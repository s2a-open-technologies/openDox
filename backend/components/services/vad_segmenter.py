"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-FileCopyrightText: 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-License-Identifier: AGPL-3.0-or-later

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

Client-side voice activity detection for the final Whisper transcription.

External Whisper servers differ: some filter silence themselves, others (e.g.
vLLM, OpenAI-style gateways) hallucinate text on silence, loop on a
``prompt``, or reject long uploads. Cutting the silence out and sending only
speech in chunks of at most ``MAX_CHUNK_S`` seconds works the same against
every server, so it is always done here, before the HTTP call.
"""

import subprocess

import numpy as np

from backend.components.modules.silero_vad import SAMPLE_RATE, get_speech_timestamps

# Whisper decodes 30 s windows; stay below so a chunk never needs splitting.
MAX_CHUNK_S = 28.0
# Short pause inserted between two speech spans packed into one chunk.
GAP_S = 0.25
DEFAULT_MIN_SILENCE_MS = 500


def decode_audio(source: bytes | np.ndarray | str) -> np.ndarray:
    """Return 16 kHz mono float32 samples for any supported audio source.

    Args:
        source: A file path (decoded with ffmpeg, any container), raw float32
            PCM bytes, or a float32 array (both assumed 16 kHz mono).

    Raises:
        RuntimeError: If ffmpeg cannot decode the file.
    """
    if isinstance(source, np.ndarray):
        return np.asarray(source, dtype=np.float32)
    if isinstance(source, bytes):
        return np.frombuffer(source, dtype=np.float32)

    proc = subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-i",
            source,
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "pipe:1",
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg could not decode audio: {proc.stderr[-300:]!r}")
    return np.frombuffer(proc.stdout, dtype=np.float32)


def segment_speech(
    audio: np.ndarray,
    min_silence_ms: int = DEFAULT_MIN_SILENCE_MS,
    max_chunk_s: float = MAX_CHUNK_S,
) -> list[np.ndarray]:
    """Cut silence out of ``audio`` and pack the speech into chunks.

    Args:
        audio: 16 kHz mono float32 samples.
        min_silence_ms: Pause length that ends a speech span.
        max_chunk_s: Upper bound for the duration of each returned chunk.

    Returns:
        Speech-only chunks in recording order; empty list if no speech found.
    """
    spans = get_speech_timestamps(
        audio,
        min_silence_ms=min_silence_ms,
        # Single spans must fit a chunk on their own.
        max_speech_s=max_chunk_s - 3.0,
    )
    gap = np.zeros(int(GAP_S * SAMPLE_RATE), dtype=np.float32)
    max_samples = max_chunk_s * SAMPLE_RATE

    chunks: list[np.ndarray] = []
    parts: list[np.ndarray] = []
    length = 0
    for span in spans:
        piece = audio[span["start"] : span["end"]]
        extra = len(piece) + (len(gap) if parts else 0)
        if parts and length + extra > max_samples:
            chunks.append(np.concatenate(parts))
            parts, length, extra = [], 0, len(piece)
        if parts:
            parts.append(gap)
        parts.append(piece)
        length += extra
    if parts:
        chunks.append(np.concatenate(parts))
    return chunks
