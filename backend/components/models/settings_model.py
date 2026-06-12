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

from typing import Optional

from sqlmodel import Field, SQLModel


class WhisperSettingsModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # Live (Near-Real-Time) Transcription Settings
    live_backend: str = Field(default="api")  # "api", "disabled"
    live_api_endpoint: Optional[str] = Field(default=None)
    live_api_key: Optional[str] = Field(default=None)
    live_api_model: Optional[str] = Field(default=None)  # e.g. "whisper-1"

    # Final Transcription Settings
    final_backend: str = Field(default="api")  # "api"
    final_api_endpoint: Optional[str] = Field(default=None)
    final_api_key: Optional[str] = Field(default=None)
    final_api_model: Optional[str] = Field(default=None)

    # Common Settings
    language: str = Field(default="de")
    chunk_length_s: int = Field(default=3)
    overlap_s: float = Field(default=0.0)

    # Anti-hallucination / faster-whisper tuning (sent to the Whisper server
    # as transcription parameters). Defaults mirror the proven config that was
    # lost when switching to an off-the-shelf container.
    temperature: float = Field(default=0.0)
    vad_filter: bool = Field(default=True)
    vad_min_silence_ms: int = Field(default=500)
    condition_on_previous_text: bool = Field(default=False)
    no_speech_threshold: float = Field(default=0.6)
    compression_ratio_threshold: float = Field(default=2.4)
    log_prob_threshold: float = Field(default=-1.0)
    hallucination_silence_threshold: Optional[float] = Field(default=2.0)
    live_beam_size: int = Field(default=1)
    final_beam_size: int = Field(default=5)
