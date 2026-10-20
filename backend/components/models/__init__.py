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

# Import all SQLModel tables for Alembic autogenerate support
from backend.components.models.audio_settings_model import AudioSettingsModel
from backend.components.models.categories import (
    Categories,
    CategoriesCreate,
    CategoriesRead,
)
from backend.components.models.client_settings_model import ClientSettingsModel
from backend.components.models.dictionary import CategoryDictionaryLink, Dictionary
from backend.components.models.encryption_key_state import EncryptionKeyState
from backend.components.models.languages import (
    Languages,
    LanguagesCreate,
    LanguagesRead,
)
from backend.components.models.ldap_model import LdapSettingsModel
from backend.components.models.llm_settings_model import LlmSettingsModel
from backend.components.models.oidc_model import OidcSettingsModel
from backend.components.models.record_model import (
    FinalizeRecord,
    Record,
    RecordChunk,
    RecordCreate,
    RecordRead,
    RecordUpdate,
)
from backend.components.models.settings_model import WhisperSettingsModel
from backend.components.models.task_model import Task
from backend.components.models.token_model import Token
from backend.components.models.user_model import User

__all__ = [
    "AudioSettingsModel",
    "Categories",
    "CategoriesCreate",
    "CategoriesRead",
    "CategoryDictionaryLink",
    "ClientSettingsModel",
    "Dictionary",
    "EncryptionKeyState",
    "Languages",
    "LanguagesCreate",
    "LanguagesRead",
    "LdapSettingsModel",
    "LlmSettingsModel",
    "OidcSettingsModel",
    "Record",
    "RecordCreate",
    "RecordUpdate",
    "RecordRead",
    "RecordChunk",
    "FinalizeRecord",
    "WhisperSettingsModel",
    "Task",
    "Token",
    "User",
]
