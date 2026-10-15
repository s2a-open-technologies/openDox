"""openDox - Medical transcription platform
Copyright (C) 2025  S2A Open Technologies gGmbH
SPDX-FileCopyrightText: 2025 S2A Open Technologies gGmbH
SPDX-FileCopyrightText: 2023 SYSTRAN
SPDX-License-Identifier: AGPL-3.0-or-later AND MIT

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Silero VAD (speech/silence detection) on top of onnxruntime.

The speech-timestamp state machine and the batched model call are adapted from
faster-whisper (``faster_whisper/vad.py``, MIT, (c) SYSTRAN), which in turn
adapts https://github.com/snakers4/silero-vad (MIT). The ONNX model
``assets/silero_vad_v6.onnx`` is the Silero VAD v6 model shipped with
faster-whisper. See THIRD_PARTY_NOTICES.md.
"""

import threading
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16000
WINDOW_SAMPLES = 512
CONTEXT_SAMPLES = 64
_MODEL_PATH = Path(__file__).resolve().parent.parent / "assets" / "silero_vad_v6.onnx"

_model = None
_model_lock = threading.Lock()


class _SileroModel:
    """Thin wrapper around the Silero VAD ONNX session (CPU, single thread)."""

    def __init__(self, path: Path):
        import onnxruntime

        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.enable_cpu_mem_arena = False
        opts.log_severity_level = 4
        self.session = onnxruntime.InferenceSession(
            str(path), providers=["CPUExecutionProvider"], sess_options=opts
        )

    def __call__(self, audio: np.ndarray) -> np.ndarray:
        """Return one speech probability per 512-sample window.

        Args:
            audio: 1-D float32 array whose length is a multiple of 512.
        """
        h = np.zeros((1, 1, 128), dtype="float32")
        c = np.zeros((1, 1, 128), dtype="float32")

        windows = audio.reshape(-1, WINDOW_SAMPLES)
        context = windows[..., -CONTEXT_SAMPLES:].copy()
        context[-1] = 0
        context = np.roll(context, 1, 0)
        batched = np.concatenate([context, windows], 1)

        outputs = []
        batch_size = 10000
        for i in range(0, batched.shape[0], batch_size):
            out, h, c = self.session.run(
                None, {"input": batched[i : i + batch_size], "h": h, "c": c}
            )
            outputs.append(out)
        return np.concatenate(outputs, axis=0)


def _get_model() -> _SileroModel:
    """Load the model once per process (thread-safe)."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = _SileroModel(_MODEL_PATH)
    return _model


def get_speech_timestamps(
    audio: np.ndarray,
    *,
    threshold: float = 0.5,
    min_speech_ms: int = 0,
    max_speech_s: float = float("inf"),
    min_silence_ms: int = 500,
    speech_pad_ms: int = 300,
) -> list[dict[str, int]]:
    """Find speech spans in 16 kHz mono float32 audio.

    Args:
        audio: 1-D float32 array at 16 kHz.
        threshold: Probability at or above which a window counts as speech.
        min_speech_ms: Spans shorter than this are dropped.
        max_speech_s: Spans longer than this are split (at a pause if possible).
        min_silence_ms: Silence needed to close a speech span.
        speech_pad_ms: Padding added on both sides of each span.

    Returns:
        List of ``{"start": sample, "end": sample}`` dicts, in order.
    """
    if audio.size == 0:
        return []

    neg_threshold = max(threshold - 0.15, 0.01)
    min_speech_samples = SAMPLE_RATE * min_speech_ms / 1000
    pad = SAMPLE_RATE * speech_pad_ms / 1000
    max_speech_samples = SAMPLE_RATE * max_speech_s - WINDOW_SAMPLES - 2 * pad
    min_silence_samples = SAMPLE_RATE * min_silence_ms / 1000
    min_silence_at_max = SAMPLE_RATE * 98 / 1000
    total = len(audio)

    padded = np.pad(audio, (0, WINDOW_SAMPLES - total % WINDOW_SAMPLES))
    probs = _get_model()(padded)

    triggered = False
    speeches: list[dict[str, int]] = []
    current: dict[str, int] = {}
    temp_end = 0
    prev_end = next_start = 0

    for i, prob in enumerate(probs):
        pos = WINDOW_SAMPLES * i
        if prob >= threshold and temp_end:
            temp_end = 0
            if next_start < prev_end:
                next_start = pos

        if prob >= threshold and not triggered:
            triggered = True
            current["start"] = pos
            continue

        if triggered and pos - current["start"] > max_speech_samples:
            if prev_end:
                current["end"] = prev_end
                speeches.append(current)
                current = {}
                if next_start < prev_end:
                    triggered = False
                else:
                    current["start"] = next_start
                prev_end = next_start = temp_end = 0
            else:
                current["end"] = pos
                speeches.append(current)
                current = {}
                prev_end = next_start = temp_end = 0
                triggered = False
                continue

        if prob < neg_threshold and triggered:
            if not temp_end:
                temp_end = pos
            if pos - temp_end > min_silence_at_max:
                prev_end = temp_end
            if pos - temp_end < min_silence_samples:
                continue
            current["end"] = temp_end
            if current["end"] - current["start"] > min_speech_samples:
                speeches.append(current)
            current = {}
            prev_end = next_start = temp_end = 0
            triggered = False

    if current and (total - current["start"]) > min_speech_samples:
        current["end"] = total
        speeches.append(current)

    for i, speech in enumerate(speeches):
        if i == 0:
            speech["start"] = int(max(0, speech["start"] - pad))
        if i != len(speeches) - 1:
            gap = speeches[i + 1]["start"] - speech["end"]
            if gap < 2 * pad:
                speech["end"] += int(gap // 2)
                nxt = speeches[i + 1]
                nxt["start"] = int(max(0, nxt["start"] - gap // 2))
            else:
                speech["end"] = int(min(total, speech["end"] + pad))
                nxt = speeches[i + 1]
                nxt["start"] = int(max(0, nxt["start"] - pad))
        else:
            speech["end"] = int(min(total, speech["end"] + pad))

    return speeches
