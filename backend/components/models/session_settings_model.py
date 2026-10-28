"""openDox - Medical transcription platform
Copyright (C) 2026  S2A Open Technologies gGmbH
SPDX-FileCopyrightText: 2026 S2A Open Technologies gGmbH
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


class SessionSettingsModel(SQLModel, table=True):
    """Server-wide login session policy for the web UI (global, one row)."""

    id: Optional[int] = Field(default=None, primary_key=True)

    # Minutes without input after which the web UI logs out; 0 = never.
    # Never applied while a recording is running.
    idle_timeout_minutes: int = Field(default=30)


class SessionConfig(SQLModel):
    """API shape of the session policy."""

    idle_timeout_minutes: int = Field(default=30, ge=0, le=1440)
