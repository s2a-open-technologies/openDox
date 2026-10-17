"""openDox - Standalone Whisper transcription server.

OpenAI-compatible faster-whisper server exposing POST /v1/audio/transcriptions.
Unlike off-the-shelf images, this server accepts the full set of faster-whisper
anti-hallucination parameters (vad_filter, condition_on_previous_text,
temperature, no_speech_threshold, …) as multipart form fields so the main
application can tune transcription per request via its settings.

Copyright (C) 2025  S2A Open Technologies gGmbH
SPDX-FileCopyrightText: 2025 S2A Open Technologies gGmbH
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
"""

import asyncio
import logging
import os
import subprocess
import tempfile

import numpy as np
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from faster_whisper import WhisperModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whisper_server")

MODEL_NAME = os.getenv("WHISPER_MODEL", "large-v3-turbo")
DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "float16")
API_KEY = os.getenv("WHISPER_API_KEY")  # optional Bearer auth

# Bounds concurrent transcribe() calls against the single shared whisper_model
# instance. Without this, every finished recording fires its own transcription
# thread with no coordination — fine at low volume, but under a burst of many
# concurrent finishes (e.g. a multi-user test session) this GPU is often
# shared with parakeet_server too, so uncoordinated concurrent Whisper calls
# can thrash/OOM instead of just queueing. Mirrors parakeet_server/streaming.py's
# MAX_CONCURRENT_DECODES pattern. Override via WHISPER_MAX_CONCURRENT_TRANSCRIPTIONS.
MAX_CONCURRENT_TRANSCRIPTIONS = int(
    os.getenv("WHISPER_MAX_CONCURRENT_TRANSCRIPTIONS", "4")
)
_transcription_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TRANSCRIPTIONS)

app = FastAPI(title="openDox Whisper Server")

logger.info(
    "Loading faster-whisper model '%s' (device=%s, compute_type=%s)…",
    MODEL_NAME,
    DEVICE,
    COMPUTE_TYPE,
)
whisper_model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE_TYPE)
logger.info("Model loaded — ready.")


def _check_auth(authorization: str | None) -> None:
    """Enforce Bearer auth when WHISPER_API_KEY is configured."""
    if not API_KEY:
        return
    expected = f"Bearer {API_KEY}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@app.get("/v1/models")
async def list_models():
    """Minimal OpenAI-compatible models endpoint (used by health checks)."""
    return {"object": "list", "data": [{"id": MODEL_NAME, "object": "model"}]}


@app.get("/health")
async def health():
    """Report server health and the loaded model name."""
    return {"status": "ok", "model": MODEL_NAME}


def _decode_audio(path: str) -> np.ndarray:
    """Decode any audio file to mono float32 PCM at 16 kHz via ffmpeg.

    faster-whisper's own ``decode_audio`` goes through PyAV and passes
    ``metadata_errors`` to ``av.open()``, which newer PyAV releases reject
    (breaking every request). Decoding here keeps the server independent of
    the installed ``av`` version.
    """
    result = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-i",
            path,
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-",
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"ffmpeg decode failed: {result.stderr.decode()[:300]}")
    return np.frombuffer(result.stdout, dtype=np.float32)


def _run_transcription(
    tmp_path: str,
    lang: str | None,
    prompt: str | None,
    beam_size: int,
    temperature: float,
    vad_filter: bool,
    vad_min_silence_ms: int,
    condition_on_previous_text: bool,
    no_speech_threshold: float,
    compression_ratio_threshold: float,
    log_prob_threshold: float,
    hallucination_silence_threshold: float | None,
) -> tuple[str, object]:
    """Run the blocking faster-whisper inference off the event loop.

    ``WhisperModel.transcribe()`` returns immediately with a lazy generator —
    the actual GPU/CPU work happens while iterating ``segments``, so both the
    call and the iteration must run inside the same ``asyncio.to_thread``
    call, not just the former, or the event loop still blocks on iteration.
    """
    segments, info = whisper_model.transcribe(
        _decode_audio(tmp_path),
        language=lang,
        initial_prompt=prompt or None,
        beam_size=beam_size,
        temperature=temperature,
        vad_filter=vad_filter,
        vad_parameters=dict(min_silence_duration_ms=vad_min_silence_ms),
        condition_on_previous_text=condition_on_previous_text,
        no_speech_threshold=no_speech_threshold,
        compression_ratio_threshold=compression_ratio_threshold,
        log_prob_threshold=log_prob_threshold,
        hallucination_silence_threshold=hallucination_silence_threshold,
    )
    text = "".join(segment.text for segment in segments).strip()
    return text, info


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form(None),  # accepted for OpenAI compat, ignored (server-fixed)
    language: str = Form("de"),
    prompt: str | None = Form(None),
    temperature: float = Form(0.0),
    vad_filter: bool = Form(True),
    vad_min_silence_ms: int = Form(500),
    condition_on_previous_text: bool = Form(False),
    no_speech_threshold: float = Form(0.6),
    compression_ratio_threshold: float = Form(2.4),
    log_prob_threshold: float = Form(-1.0),
    hallucination_silence_threshold: float | None = Form(None),
    beam_size: int = Form(5),
    authorization: str | None = Header(None),
):
    """Transcribe an uploaded audio file with full anti-hallucination control."""
    _check_auth(authorization)

    audio_bytes = await file.read()
    if not audio_bytes:
        return {"text": ""}

    # faster-whisper needs a path/file-like; write to a temp file (server decodes)
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        lang = None if (not language or language.lower() == "auto") else language
        async with _transcription_semaphore:
            text, info = await asyncio.to_thread(
                _run_transcription,
                tmp_path,
                lang,
                prompt,
                beam_size,
                temperature,
                vad_filter,
                vad_min_silence_ms,
                condition_on_previous_text,
                no_speech_threshold,
                compression_ratio_threshold,
                log_prob_threshold,
                hallucination_silence_threshold,
            )
        logger.info(
            "Transcribed %d bytes | lang=%s vad=%s cond_prev=%s -> %d chars",
            len(audio_bytes),
            info.language if info else lang,
            vad_filter,
            condition_on_previous_text,
            len(text),
        )
        return {"text": text}
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
