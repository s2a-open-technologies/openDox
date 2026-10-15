"""Tests for the client-side VAD segmentation used before Whisper calls."""

import shutil
import wave
from pathlib import Path

import numpy as np
import pytest

from backend.components.services import vad_segmenter
from backend.components.services.vad_segmenter import (
    MAX_CHUNK_S,
    decode_audio,
    segment_speech,
)

SR = 16000
FIXTURE = Path(__file__).parent.parent / "fixtures" / "speech_pause_de.wav"


def _fixture_audio() -> np.ndarray:
    with wave.open(str(FIXTURE)) as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768


def test_silence_yields_no_chunks():
    assert segment_speech(np.zeros(SR * 10, dtype=np.float32)) == []


def test_empty_audio_yields_no_chunks():
    assert segment_speech(np.array([], dtype=np.float32)) == []


def test_low_noise_yields_no_chunks():
    rng = np.random.default_rng(0)
    noise = (rng.normal(0, 0.001, SR * 10)).astype(np.float32)
    assert segment_speech(noise) == []


def test_real_speech_is_kept_and_pause_is_cut():
    audio = _fixture_audio()  # ~8 s: sentence, 3 s silence, sentence
    chunks = segment_speech(audio)
    assert chunks, "speech must be detected"
    kept = sum(len(c) for c in chunks) / SR
    total = len(audio) / SR
    assert kept < total - 2.0, "the 3 s pause must be removed"
    assert kept > 3.5, "both sentences must survive"
    assert all(len(c) / SR <= MAX_CHUNK_S for c in chunks)


def test_long_speech_is_split_below_limit_and_keeps_order(monkeypatch):
    audio = np.concatenate(
        [np.full(SR * 10, v, dtype=np.float32) for v in (0.1, 0.2, 0.3, 0.4)]
    )
    spans = [{"start": i * SR * 10, "end": (i + 1) * SR * 10} for i in range(4)]
    monkeypatch.setattr(vad_segmenter, "get_speech_timestamps", lambda *a, **k: spans)

    chunks = segment_speech(audio)

    assert len(chunks) == 2  # 10 s + gap + 10 s fits 28 s, three spans do not
    assert all(len(c) / SR <= MAX_CHUNK_S for c in chunks)
    assert chunks[0][0] == pytest.approx(0.1) and chunks[1][0] == pytest.approx(0.3)
    assert chunks[1][-1] == pytest.approx(0.4)


def test_decode_accepts_pcm_bytes_and_arrays():
    pcm = np.linspace(-0.5, 0.5, 100, dtype=np.float32)
    assert np.array_equal(decode_audio(pcm.tobytes()), pcm)
    assert np.array_equal(decode_audio(pcm), pcm)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_decode_file_resamples_to_16khz_mono():
    audio = decode_audio(str(FIXTURE))
    assert audio.dtype == np.float32
    assert len(audio) / SR == pytest.approx(len(_fixture_audio()) / SR, abs=0.1)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_decode_missing_file_raises():
    with pytest.raises(RuntimeError):
        decode_audio("/nonexistent/file.wav")
