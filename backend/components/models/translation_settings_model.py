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

from sqlmodel import Field, SQLModel

# Dictation languages offered by default (ISO 639-1), the ones covered by
# bench/translation_bench.py.
DEFAULT_TRANSLATION_LANGUAGES = "ru,uk,pl,ro,bg,sr,ar"


class TranslationSettingsModel(SQLModel, table=True):
    """Dictation in another language, translated into the instance language.

    Off by default: the operator decides consciously (docs/zweckbestimmung.md).
    The target language is not stored here, it is always the transcription
    language of the instance (WhisperSettingsModel.language).
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    enabled: bool = Field(default=False)
    # "all" = every user; "selected" = only users with User.translation_allowed.
    access: str = Field(default="selected")
    # Comma-separated ISO codes of the dictation languages users may pick.
    languages: str = Field(default=DEFAULT_TRANSLATION_LANGUAGES)


def split_languages(raw: str | None) -> list[str]:
    """Return the stored comma-separated language list as clean ISO codes."""
    return [code.strip().lower() for code in (raw or "").split(",") if code.strip()]


class TranslationConfig(SQLModel):
    """Admin API shape of the translation settings."""

    enabled: bool = False
    access: Literal["all", "selected"] = "selected"
    languages: list[str] = Field(default_factory=list)
    # Read-only: the instance language everything is translated into.
    target_language: str = "de"


class TranslationAvailability(SQLModel):
    """What the current user may use (``GET /settings/translation/me``)."""

    available: bool
    languages: list[str]
    target_language: str
    # Subset of ``languages`` with live preview while recording.
    live_languages: list[str] = []
