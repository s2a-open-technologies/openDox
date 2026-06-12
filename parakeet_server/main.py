"""openDox - Parakeet ASR Server

Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

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

# Standard library
import os
import struct
import tempfile
from contextlib import asynccontextmanager

# Third-party imports
import onnx_asr
import numpy as np
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

DEFAULT_MODEL = os.getenv("PARAKEET_MODEL", "nemo-parakeet-tdt-0.6b-v3")

_models: dict[str, "onnx_asr.adapters.TextResultsAsrAdapter"] = {}


def get_model(name: str | None = None) -> "onnx_asr.adapters.TextResultsAsrAdapter":
    """Load and cache an ONNX ASR model by name.

    Models are loaded on first request and kept in memory for subsequent
    requests. The default model is pre-loaded during application startup
    via the lifespan handler.

    Args:
        name: Model identifier (e.g. 'nemo-parakeet-tdt-0.6b-v3').
              Falls back to the PARAKEET_MODEL environment variable,
              then to DEFAULT_MODEL.

    Returns:
        The loaded and cached model instance.

    Raises:
        RuntimeError: If the model cannot be loaded.
    """
    model_name = name or DEFAULT_MODEL

    if model_name in _models:
        return _models[model_name]

    print(f"[PARAKEET] Loading model: {model_name} ...")
    try:
        _models[model_name] = onnx_asr.load_model(model_name)
    except Exception as e:
        raise RuntimeError(f"Failed to load model '{model_name}': {e}") from e

    print(f"[PARAKEET] Model loaded: {model_name}")
    return _models[model_name]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler: load the default model on startup, unload on shutdown."""
    get_model()
    yield
    _models.clear()
    print("[PARAKEET] Models unloaded")


app = FastAPI(title="openDox Parakeet ASR", lifespan=lifespan)


@app.get("/v1/models")
async def list_models():
    """List available models.

    Returns:
        OpenAI-compatible /v1/models response with the default model.
    """
    return {"data": [{"id": DEFAULT_MODEL, "object": "model"}]}


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form(default=""),
    language: str = Form(default=""),
):
    """Transcribe audio using the Parakeet ONNX ASR model.

    OpenAI-compatible endpoint that accepts WAV or raw PCM audio
    (float32, 16 kHz, mono) and returns transcribed text with
    punctuation and capitalization.

    Args:
        file: Audio file (WAV or raw PCM).
        model: Model name to use (optional, defaults to PARAKEET_MODEL).
        language: Language hint (optional, currently unused by Parakeet).

    Returns:
        JSON response with a "text" field containing the transcription.
    """
    content = await file.read()
    if not content:
        return JSONResponse({"text": ""})

    wav_bytes = content if content[:4] == b"RIFF" else _pcm_to_wav(content)

    m = get_model(model or None)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        tmp.write(wav_bytes)
        tmp.flush()
        try:
            result = m.recognize(tmp.name)
            text = result if isinstance(result, str) else str(result)
        except Exception as e:
            print(f"[PARAKEET] Recognition error: {e}")
            text = ""

    return {"text": text}


def _pcm_to_wav(pcm: bytes) -> bytes:
    """Convert raw float32 16kHz mono PCM bytes to a WAV file in memory.

    Takes raw PCM sample data as bytes (float32 little-endian, 16 kHz,
    mono) and wraps it in a standard WAV file header.

    Args:
        pcm: Raw PCM audio data as float32 little-endian bytes.

    Returns:
        Complete WAV file as bytes (header + PCM int16 data).
    """

    audio = np.frombuffer(pcm, dtype=np.float32)
    audio = np.clip(audio, -1.0, 1.0)
    pcm_int16 = (audio * 32767).astype(np.int16)

    num_channels = 1
    sample_rate = 16000
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = len(pcm_int16) * 2

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )

    return header + pcm_int16.tobytes()