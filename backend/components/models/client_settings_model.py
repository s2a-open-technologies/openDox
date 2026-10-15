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

from typing import Literal, Optional

from pydantic import field_validator
from sqlmodel import Field, SQLModel

DictationMicMode = Literal["hold", "toggle"]


class ClientSettingsModel(SQLModel, table=True):
    """Server-wide policy for the openDox desktop client (global, one row).

    The client fetches it via ``GET /api/v1/settings/client-config/`` and lets
    it override its local ``settings.json``. ``insert_allowlist`` is stored as
    newline-separated text; the API exposes it as a list (``ClientConfig``).
    """

    id: Optional[int] = Field(default=None, primary_key=True)

    clipboard_exclude_from_history: bool = Field(default=True)

    clipboard_clear_after_seconds: int = Field(default=30)

    insert_allowlist: str = Field(default="")

    dictation_mic_mode: str = Field(default="hold")

    live_view: bool = Field(default=True)


class ClientConfig(SQLModel):
    """API shape of the client policy — same keys as the client's settings.json."""

    clipboard_exclude_from_history: bool = True
    clipboard_clear_after_seconds: int = Field(default=30, ge=0)
    insert_allowlist: list[str] = []
    dictation_mic_mode: DictationMicMode = "hold"
    live_view: bool = True

    @field_validator("insert_allowlist")
    @classmethod
    def _clean_allowlist(cls, entries: list[str]) -> list[str]:
        """Trim entries, drop empty ones and case-insensitive duplicates."""
        cleaned: list[str] = []
        seen: set[str] = set()
        for entry in entries:
            value = entry.strip()
            if value and value.lower() not in seen:
                seen.add(value.lower())
                cleaned.append(value)
        return cleaned

    @classmethod
    def from_row(cls, row: ClientSettingsModel) -> "ClientConfig":
        """Build the API shape from the stored row."""
        return cls(
            clipboard_exclude_from_history=row.clipboard_exclude_from_history,
            clipboard_clear_after_seconds=row.clipboard_clear_after_seconds,
            insert_allowlist=row.insert_allowlist.splitlines(),
            dictation_mic_mode=row.dictation_mic_mode,
            live_view=row.live_view,
        )

    def apply_to(self, row: ClientSettingsModel) -> None:
        """Write these values into the stored row (allowlist as text lines)."""
        row.clipboard_exclude_from_history = self.clipboard_exclude_from_history
        row.clipboard_clear_after_seconds = self.clipboard_clear_after_seconds
        row.insert_allowlist = "\n".join(self.insert_allowlist)
        row.dictation_mic_mode = self.dictation_mic_mode
        row.live_view = self.live_view
