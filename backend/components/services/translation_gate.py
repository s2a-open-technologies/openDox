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

Who may dictate in another language, and into which language it is translated.

The translation is an operator decision (docs/zweckbestimmung.md): off by
default, then released for every user or for selected ones. It needs the LLM,
so it is never available while the global LLM switch is off. The target is
always the transcription language of the instance, not a separate setting.
"""

# Third party
from sqlmodel import Session, select

# Custom
from backend.components.models.settings_model import WhisperSettingsModel
from backend.components.models.translation_settings_model import (
    TranslationSettingsModel,
    split_languages,
)
from backend.components.models.user_model import User
from backend.components.modules.api_errors import api_error
from backend.components.services.llm_gate import llm_globally_enabled

DEFAULT_TARGET_LANGUAGE = "de"

# Languages the live preview model (nemo-parakeet-tdt-0.6b-v3) recognises on
# its own. Dictation in any other language records without live text; the
# final transcription (Whisper) is unaffected.
LIVE_LANGUAGES = frozenset(
    {
        "bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr", "hr", "hu",
        "it", "lt", "lv", "mt", "nl", "pl", "pt", "ro", "ru", "sk", "sl", "sv",
        "uk",
    }
)  # fmt: skip


def live_preview_supported(language: str | None) -> bool:
    """Whether the live preview can show text for this dictation language."""
    return not language or language.lower() in LIVE_LANGUAGES


def translation_settings(db: Session) -> TranslationSettingsModel:
    """Return the stored settings row, or the defaults if there is none."""
    return db.exec(select(TranslationSettingsModel)).first() or (
        TranslationSettingsModel()
    )


def target_language(db: Session) -> str:
    """Return the instance language every dictation is translated into."""
    whisper = db.exec(select(WhisperSettingsModel)).first()
    language = (whisper.language if whisper else "") or DEFAULT_TARGET_LANGUAGE
    return language.strip().lower()


def translation_available(db: Session, user: User) -> bool:
    """Return whether ``user`` may dictate in another language.

    Never while the instance language is not a plain ISO code (e.g. "auto"):
    there would be nothing definite to translate into.
    """
    settings = translation_settings(db)
    if not settings.enabled or not llm_globally_enabled(db):
        return False
    if len(target_language(db)) != 2:
        return False
    return settings.access == "all" or bool(user.translation_allowed)


def offered_languages(db: Session) -> list[str]:
    """Dictation languages users may pick, never the target language itself."""
    target = target_language(db)
    return [
        code
        for code in split_languages(translation_settings(db).languages)
        if code != target
    ]


def resolve_source_language(db: Session, user: User, code: str | None) -> str | None:
    """Validate a requested dictation language for a new recording.

    Returns:
        The normalized code if the recording is to be translated, None if it
        is dictated in the instance language (empty or equal to the target).

    Raises:
        HTTPException: 403 ``translation_not_available`` if the user may not
            translate or the language is not offered.
    """
    code = (code or "").strip().lower()
    if not code or code == target_language(db):
        return None
    if not translation_available(db, user) or code not in offered_languages(db):
        raise api_error(
            403,
            "translation_not_available",
            "Dictation in this language is not available",
            language=code,
        )
    return code
