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

from abc import ABC, abstractmethod

import numpy as np


class ASRBackend(ABC):
    """Abstract base class for ASR (Automatic Speech Recognition) backends.

    Supports API-based transcription services.
    """

    @abstractmethod
    def transcribe(
        self,
        audio: bytes | np.ndarray | str,
        language: str = "de",
        beam_size: int = 5,
        prompt: str | None = None,
        params: dict | None = None,
    ) -> str:
        """Transcribe audio to text.

        Args:
            audio: Audio data (PCM bytes, numpy array) or file path
            language: Language code (e.g., 'de', 'en')
            beam_size: Beam size for decoding (lower = faster)
            prompt: Optional text prompt for context continuation
                (Whisper / API backends)
            params: Optional extra transcription parameters (vad_filter,
                temperature, …) forwarded to backends that support them.

        Returns:
            Transcribed text
        """
        pass

    @abstractmethod
    def supports_streaming(self) -> bool:
        """Whether this backend supports real-time streaming.

        For truly streaming APIs (like Voxtral or live WebSocket connections),
        this should return True. Most REST APIs return False.
        """
        return False

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the backend is healthy and available.

        Returns:
            True if backend is ready to transcribe
        """
        pass
