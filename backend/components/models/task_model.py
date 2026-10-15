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

# models/task.py
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Task(SQLModel, table=True):
    """Background transcription task model."""

    id: int = Field(default=None, primary_key=True)
    status: str = Field(default="pending")  # pending, running, done, error
    result: Optional[str] = None
    error: Optional[str] = None
    retry_audio_path: Optional[str] = None
    # When True, retry_audio_path holds an S3 object key (see
    # failed_audio_archival_service.py) instead of a local filesystem path —
    # the local chunks/failed/ file was archived after FAILED_AUDIO_RETENTION_DAYS.
    retry_audio_in_s3: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
