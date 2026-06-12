"""openDox - Medical transcription platform
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

import numpy as np

from .base import ASRBackend


class DisabledBackend(ASRBackend):
    """Placeholder backend when transcription is disabled.

    Returns empty strings for all transcriptions.
    Useful for disabling live transcription while keeping final transcription active.
    """

    def __init__(self):
        pass

    def transcribe(
        self,
        audio: bytes | np.ndarray | str,
        language: str = "de",
        beam_size: int = 5,
        prompt: str | None = None,
        params: dict | None = None,
    ) -> str:
        """Return empty string (transcription disabled)."""
        return ""

    def supports_streaming(self) -> bool:
        """Disabled backend does not support streaming."""
        return False

    def health_check(self) -> bool:
        """Always healthy (does nothing)."""
        return True

    def get_chunk_config(self) -> dict:
        """Return default config (not used when disabled)."""
        return {
            "chunk_length_s": 5,
            "overlap_s": 0,
        }
