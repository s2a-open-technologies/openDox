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

import io
import os
import struct
import tempfile

import onnx_asr
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

MODEL_NAME = os.getenv("PARAKEET_MODEL", "nemo-parakeet-tdt-0.6b-v3")

app = FastAPI(title="openDox Parakeet ASR")

_model = None


def get_model():
    global _model
    if _model is None:
        print(f"[PARAKEET] Loading model: {MODEL_NAME} ...")
        _model = onnx_asr.load_model(MODEL_NAME)
        print(f"[PARAKEET] Model loaded: {MODEL_NAME}")
    return _model


@app.on_event("startup")
async def startup():
    get_model()


@app.get("/v1/models")
async def list_models():
    return {"data": [{"id": MODEL_NAME, "object": "model"}]}


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form(default=""),
    language: str = Form(default=""),
):
    """OpenAI-compatible /v1/audio/transcriptions endpoint.

    Accepts WAV or raw PCM (float32 16kHz mono) audio and returns
    transcribed text with punctuation and capitalization.
    """
    content = await file.read()
    if not content:
        return JSONResponse({"text": ""})

    # Detect format: WAV starts with b"RIFF", anything else is raw PCM.
    wav_bytes = content if content[:4] == b"RIFF" else _pcm_to_wav(content)

    m = get_model()

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
    """Convert raw float32 16kHz mono PCM to a WAV file in memory."""
    import numpy as np

    audio = np.frombuffer(pcm, dtype=np.float32)

    # Clamp and convert to int16
    audio = np.clip(audio, -1.0, 1.0)
    pcm_int16 = (audio * 32767).astype(np.int16)

    num_channels = 1
    sample_rate = 16000
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = len(pcm_int16) * 2  # int16 = 2 bytes

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