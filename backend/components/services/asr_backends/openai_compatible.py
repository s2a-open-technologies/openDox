"""openDox - Medical transcription platform
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

import struct
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import requests

from backend.components.modules.audio import normalize_quiet_pcm
from backend.components.modules.logger import get_logger
from backend.components.services.vad_segmenter import (
    DEFAULT_MIN_SILENCE_MS,
    decode_audio,
    segment_speech,
)

from .base import ASRBackend

logger = get_logger(__name__)


class OpenAICompatibleBackend(ASRBackend):
    """API-based ASR backend compatible with OpenAI API format.

    Supports any OpenAI-compatible transcription endpoint. Before upload the
    audio is run through a client-side voice activity detection: silence is cut
    out and the speech is sent as WAV chunks of at most 28 s, in parallel. This
    behaves the same against every server (some hallucinate on silence, loop on
    a prompt or reject long uploads) and means silence is never transcribed.
    """

    # Sample rate expected by the pipeline (WebSocket delivers 16kHz float32 PCM)
    SAMPLE_RATE = 16000
    # Chunks of one recording sent to the server at the same time.
    MAX_PARALLEL_CHUNKS = 4
    # Extra attempts after a connection error / timeout (stale keep-alive etc.).
    CONNECTION_RETRIES = 2

    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        model: str = "large-v3-turbo",
        timeout: int = 60,
    ):
        """Initialize OpenAI-compatible backend.

        Args:
            endpoint: Base API URL (e.g., "http://localhost:5002")
            api_key: API key for authentication (if required)
            model: Model identifier for the API
            timeout: Request timeout in seconds
        """
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

        if "/audio/transcriptions" in self.endpoint:
            pass
        elif self.endpoint.endswith("/v1"):
            self.endpoint = f"{self.endpoint}/audio/transcriptions"
        else:
            self.endpoint = f"{self.endpoint}/v1/audio/transcriptions"

    def _pcm_to_wav(self, audio: bytes | np.ndarray) -> bytes:
        """Convert float32 PCM to a valid WAV file bytes.

        Returns WAV file bytes (RIFF header + int16 data)
        """
        if isinstance(audio, bytes):
            float_array = np.frombuffer(audio, dtype=np.float32)
        else:
            float_array = np.asarray(audio, dtype=np.float32)

        float_array = normalize_quiet_pcm(float_array)

        # Float32 (-1.0 to 1.0) -> int16
        int16_array = (float_array * 32767).astype(np.int16)

        # Build WAV header
        num_channels = 1
        sample_rate = self.SAMPLE_RATE
        byte_rate = sample_rate * num_channels * 2  # 16-bit = 2 bytes
        block_align = num_channels * 2
        bits_per_sample = 16
        data_size = len(int16_array) * 2

        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",  # ChunkID
            36 + data_size,  # ChunkSize
            b"WAVE",  # Format
            b"fmt ",  # Subchunk1ID
            16,  # Subchunk1Size
            1,  # AudioFormat (PCM)
            num_channels,  # NumChannels
            sample_rate,  # SampleRate
            byte_rate,  # ByteRate
            block_align,  # BlockAlign
            bits_per_sample,  # BitsPerSample
            b"data",  # Subchunk2ID
            data_size,  # Subchunk2Size
        )

        return header + int16_array.tobytes()

    def _post_chunk(
        self,
        wav_bytes: bytes,
        language: str,
        beam_size: int,
        prompt: str | None,
        params: dict | None,
    ) -> str:
        """Send one WAV chunk and return its text.

        Raises:
            RuntimeError: On a non-200 answer or an unexpected response format.
            requests.exceptions.RequestException: If the server stays unreachable.
        """
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        files = {
            "file": ("audio.wav", wav_bytes, "audio/wav"),
            "model": (None, self.model),
        }

        # beam_size from the params dict (if provided) takes precedence
        if not (params and "beam_size" in params):
            files["beam_size"] = (None, str(beam_size))

        if language and language.lower() != "auto":
            files["language"] = (None, language)

        if prompt:
            files["prompt"] = (None, prompt)

        # Forward tuning parameters as form fields (booleans as "true"/"false",
        # None values skipped so the server keeps its own default).
        for key, value in (params or {}).items():
            if value is None:
                continue
            if isinstance(value, bool):
                value = "true" if value else "false"
            files[key] = (None, str(value))

        for attempt in range(self.CONNECTION_RETRIES + 1):
            try:
                response = requests.post(
                    self.endpoint, headers=headers, files=files, timeout=self.timeout
                )
                break
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ):
                if attempt == self.CONNECTION_RETRIES:
                    raise
                time.sleep(0.5 * (attempt + 1))

        if response.status_code != 200:
            raise RuntimeError(f"API error: {response.status_code} - {response.text}")

        result = response.json()
        if "text" in result:
            return result["text"].strip()
        if "transcription" in result:
            return result["transcription"].strip()
        raise RuntimeError(f"Unexpected API response format: {result}")

    def transcribe(
        self,
        audio: bytes | np.ndarray | str,
        language: str = "de",
        beam_size: int = 5,
        prompt: str | None = None,
        params: dict | None = None,
    ) -> str:
        """Transcribe audio using OpenAI-compatible API.

        Silence is removed locally first; only speech is sent to the server.

        Args:
            audio: Audio data (PCM bytes, numpy array) or file path
            language: Language code
            beam_size: Beam size forwarded to the server
            prompt: Optional prompt for context continuation (sent per chunk)
            params: Extra anti-hallucination / faster-whisper parameters sent as
                form fields (vad_filter, temperature, condition_on_previous_text,
                no_speech_threshold, …). Unknown fields are ignored by servers
                that don't support them. ``vad_min_silence_ms`` additionally
                sets the pause length of the local voice activity detection.

        Returns:
            Transcribed text. Empty if no speech was found or if any chunk
            failed (a partial transcript is never returned silently).
        """
        try:
            samples = decode_audio(audio)
            min_silence = int(
                (params or {}).get("vad_min_silence_ms") or DEFAULT_MIN_SILENCE_MS
            )
            chunks = segment_speech(samples, min_silence_ms=min_silence)
        except Exception as e:
            logger.error(f"Error preparing audio for ASR API: {e}")
            return ""

        if not chunks:
            logger.info("No speech detected, skipping ASR API call")
            return ""

        logger.info(
            f"VAD: {len(samples) / self.SAMPLE_RATE:.1f}s audio -> "
            f"{sum(len(c) for c in chunks) / self.SAMPLE_RATE:.1f}s speech "
            f"in {len(chunks)} chunk(s)"
        )

        def send(chunk: np.ndarray) -> str:
            return self._post_chunk(
                self._pcm_to_wav(chunk), language, beam_size, prompt, params
            )

        try:
            with ThreadPoolExecutor(
                max_workers=min(self.MAX_PARALLEL_CHUNKS, len(chunks))
            ) as pool:
                texts = list(pool.map(send, chunks))  # keeps recording order
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error to ASR API: {e}")
            return ""
        except Exception as e:
            logger.error(f"Error calling ASR API: {e}")
            return ""

        return " ".join(t for t in texts if t)

    def supports_streaming(self) -> bool:
        """REST API does not support true streaming without WebSocket support."""
        return False

    def health_check(self) -> bool:
        """Check if API endpoint is reachable."""
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = requests.get(
                self.endpoint.replace("/audio/transcriptions", "/models"),
                headers=headers,
                timeout=5,
            )
            return response.status_code in [200, 404]
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
