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

from typing import Optional

from sqlmodel import Field, SQLModel


class AudioSettingsModel(SQLModel, table=True):
    """Settings for audio download functionality (MP3 format, mono)."""

    id: Optional[int] = Field(default=None, primary_key=True)

    audio_download_enabled: bool = Field(default=True)

    audio_bitrate: Optional[str] = Field(default="64k")

    audio_sample_rate: Optional[int] = Field(default=16000)

    audio_format: Optional[str] = Field(default="mp3")

    auto_archive_enabled: bool = Field(default=False)

    auto_archive_days: int = Field(default=90)
