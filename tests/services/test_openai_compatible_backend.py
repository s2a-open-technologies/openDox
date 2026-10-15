"""Tests for the OpenAI-compatible ASR backend with local VAD chunking."""

import numpy as np
import pytest
import requests

from backend.components.services.asr_backends import openai_compatible as mod
from backend.components.services.asr_backends.openai_compatible import (
    OpenAICompatibleBackend,
)

SR = 16000


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body if body is not None else {"text": " hallo "}
        self.text = str(self._body)

    def json(self):
        return self._body


@pytest.fixture
def backend():
    return OpenAICompatibleBackend("http://asr.test:9000", model="m")


@pytest.fixture
def audio():
    return np.full(SR * 5, 0.1, dtype=np.float32)


def _chunks(n):
    return [np.full(SR, 0.1 * (i + 1), dtype=np.float32) for i in range(n)]


def test_endpoint_is_normalised(backend):
    assert backend.endpoint == "http://asr.test:9000/v1/audio/transcriptions"


def test_no_speech_means_no_server_call(backend, audio, monkeypatch):
    monkeypatch.setattr(mod, "segment_speech", lambda *a, **k: [])
    monkeypatch.setattr(
        mod.requests, "post", lambda *a, **k: pytest.fail("server must not be called")
    )
    assert backend.transcribe(audio) == ""


def test_chunks_are_joined_in_recording_order(backend, audio, monkeypatch):
    monkeypatch.setattr(mod, "segment_speech", lambda *a, **k: _chunks(3))
    seen = []

    def fake_post(url, headers, files, timeout):
        wav = files["file"][1]
        seen.append(wav)
        # order of results is derived from the audio amplitude of the chunk
        level = int.from_bytes(wav[44:46], "little", signed=True)
        return FakeResponse(body={"text": f"chunk{round(level / 3277)}"})

    monkeypatch.setattr(mod.requests, "post", fake_post)

    assert backend.transcribe(audio) == "chunk1 chunk2 chunk3"
    assert len(seen) == 3


def test_prompt_language_and_params_are_sent_for_every_chunk(
    backend, audio, monkeypatch
):
    monkeypatch.setattr(mod, "segment_speech", lambda *a, **k: _chunks(2))
    sent = []
    monkeypatch.setattr(
        mod.requests,
        "post",
        lambda url, headers, files, timeout: sent.append(files) or FakeResponse(),
    )

    backend.transcribe(
        audio,
        prompt="Ramipril",
        params={"temperature": 0.0, "vad_filter": True, "none_val": None},
    )

    assert len(sent) == 2
    for files in sent:
        assert files["prompt"] == (None, "Ramipril")
        assert files["language"] == (None, "de")
        assert files["vad_filter"] == (None, "true")
        assert files["temperature"] == (None, "0.0")
        assert "none_val" not in files


def test_vad_min_silence_ms_param_reaches_segmenter(backend, audio, monkeypatch):
    got = {}

    def fake_segment(samples, min_silence_ms):
        got["ms"] = min_silence_ms
        return _chunks(1)

    monkeypatch.setattr(mod, "segment_speech", fake_segment)
    monkeypatch.setattr(mod.requests, "post", lambda *a, **k: FakeResponse())

    backend.transcribe(audio, params={"vad_min_silence_ms": 800})
    assert got["ms"] == 800


def test_connection_error_is_retried(backend, audio, monkeypatch):
    monkeypatch.setattr(mod, "segment_speech", lambda *a, **k: _chunks(1))
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def flaky(url, headers, files, timeout):
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.exceptions.ConnectionError("reset")
        return FakeResponse()

    monkeypatch.setattr(mod.requests, "post", flaky)

    assert backend.transcribe(audio) == "hallo"
    assert calls["n"] == 3


def test_failed_chunk_returns_empty_not_partial_text(backend, audio, monkeypatch):
    monkeypatch.setattr(mod, "segment_speech", lambda *a, **k: _chunks(3))

    def post(url, headers, files, timeout):
        level = int.from_bytes(files["file"][1][44:46], "little", signed=True)
        if round(level / 3277) == 2:
            return FakeResponse(status=500)
        return FakeResponse()

    monkeypatch.setattr(mod.requests, "post", post)

    assert backend.transcribe(audio) == ""


def test_unreadable_audio_returns_empty(backend):
    assert backend.transcribe("/nonexistent/file.wav") == ""


def test_api_key_is_sent_as_bearer(audio, monkeypatch):
    backend = OpenAICompatibleBackend("http://asr.test/v1", api_key="secret")
    monkeypatch.setattr(mod, "segment_speech", lambda *a, **k: _chunks(1))
    headers_seen = {}

    def post(url, headers, files, timeout):
        headers_seen.update(headers)
        return FakeResponse()

    monkeypatch.setattr(mod.requests, "post", post)
    backend.transcribe(audio)
    assert headers_seen["Authorization"] == "Bearer secret"
