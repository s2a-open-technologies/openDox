"""
  openDox - Medical transcription platform
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
import struct
import tempfile
import numpy as np
import requests
from typing import Optional

from .base import ASRBackend
from backend.components.modules.logger import get_logger

logger = get_logger(__name__)


class OpenAICompatibleBackend(ASRBackend):
    """API-based ASR backend compatible with OpenAI API format.
    
    Supports any OpenAI-compatible transcription endpoint.
    Audio is converted to a proper WAV file before upload.
    """
    
    # Sample rate expected by the pipeline (WebSocket delivers 16kHz float32 PCM)
    SAMPLE_RATE = 16000
    
    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        model: str = "whisper-1",
        timeout: int = 60,
    ):
        """Initialize OpenAI-compatible backend.
        
        Args:
            endpoint: Base API URL (e.g., "http://localhost:9000")
            api_key: API key for authentication (if required)
            model: Model identifier for the API
            timeout: Request timeout in seconds
        """
        self.endpoint = endpoint.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        
        if '/audio/transcriptions' in self.endpoint:
            pass
        elif self.endpoint.endswith('/v1'):
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
            '<4sI4s4sIHHIIHH4sI',
            b'RIFF',                       # ChunkID
            36 + data_size,                # ChunkSize
            b'WAVE',                       # Format
            b'fmt ',                       # Subchunk1ID
            16,                            # Subchunk1Size
            1,                             # AudioFormat (PCM)
            num_channels,                  # NumChannels
            sample_rate,                   # SampleRate
            byte_rate,                     # ByteRate
            block_align,                   # BlockAlign
            bits_per_sample,               # BitsPerSample
            b'data',                       # Subchunk2ID
            data_size                      # Subchunk2Size
        )
        
        return header + int16_array.tobytes()
    
    def _prepare_audio_file(
        self,
        audio: bytes | np.ndarray | str,
    ) -> tuple[bytes, str]:
        """Prepare audio data as a file-like payload for multipart upload.
        
        Returns (file_bytes, filename) tuple.
        """
        if isinstance(audio, str):
            # File path – read raw bytes, server decodes via ffmpeg
            ext = audio.split('.')[-1] if '.' in audio else 'wav'
            with open(audio, 'rb') as f:
                return f.read(), f"audio.{ext}"
        
        # Convert bytes/numpy to a proper WAV file
        wav_bytes = self._pcm_to_wav(audio)
        return wav_bytes, "audio.wav"
    
    def transcribe(
        self,
        audio: bytes | np.ndarray | str,
        language: str = "de",
        beam_size: int = 5,
        prompt: str | None = None,
    ) -> str:
        """Transcribe audio using OpenAI-compatible API.
        
        Args:
            audio: Audio data (PCM bytes, numpy array) or file path
            language: Language code
            beam_size: Ignored for API backends
            prompt: Optional prompt for context continuation
            
        Returns:
            Transcribed text
        """
        audio_bytes, filename = self._prepare_audio_file(audio)
        
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        files = {
            'file': (filename, audio_bytes, 'audio/wav'),
            'model': (None, self.model),
        }
        
        if language and language.lower() != "auto":
            files['language'] = (None, language)
        
        if prompt:
            files['prompt'] = (None, prompt)
        
        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                files=files,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'text' in result:
                    return result['text'].strip()
                elif 'transcription' in result:
                    return result['transcription'].strip()
                else:
                    logger.warning(f"Unexpected API response format: {result}")
                    return str(result)
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return ""
                
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error to ASR API: {e}")
            return ""
        except Exception as e:
            logger.error(f"Error calling ASR API: {e}")
            return ""
    
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
                self.endpoint.replace('/audio/transcriptions', '/models'),
                headers=headers,
                timeout=5
            )
            return response.status_code in [200, 404]
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
    
    def get_chunk_config(self) -> dict:
        """For API backends, use larger chunks to reduce HTTP overhead."""
        return {
            "chunk_length_s": 5,
            "overlap_s": 0,
        }