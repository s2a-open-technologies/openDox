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

# models/user.py
from datetime import datetime
from typing import Optional

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from backend.components.security.field_encryption import EncryptedString

# Valid role values. ``admin`` supersedes the legacy ``is_superuser=True``.
# ``demo_viewer``: sieht alle Admin-Bereiche, aber nur lesend (Demo-Zwecke);
# einzig Kategorien bleiben für diese Rolle bearbeitbar.
ROLES = ("admin", "moderator", "demo_viewer", "user")

# UI languages the frontend ships translations for (frontend/src/i18n). Add a
# code here together with its locale folder. Not to be confused with the
# transcription language (WhisperSettingsModel.language).
UI_LANGUAGES = ("de", "en")

# Where a user logs in. Decides how a session renewal re-checks the account
# (services/session_revalidation.py).
AUTH_SOURCES = ("local", "ldap", "oidc")


class User(SQLModel, table=True):
    """User model for authentication and role management."""

    id: Optional[int] = Field(primary_key=True, default=None)
    name: str = Field(index=True, unique=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    role: str = Field(default="user", index=True)
    disclaimer_accepted_at: Optional[datetime] = Field(default=None)
    # Preferred UI language (one of UI_LANGUAGES); None = not chosen yet, the
    # frontend then falls back to the browser language.
    ui_language: Optional[str] = Field(default=None)
    # One of AUTH_SOURCES, set on every login; None = not logged in since the
    # column was added, treated like "local".
    auth_source: Optional[str] = Field(default=None)
    # The OIDC provider's refresh token from the last login, used to re-check
    # the account at the provider when the session is renewed. Never exposed.
    idp_refresh_token: Optional[str] = Field(
        default=None, sa_column=Column(EncryptedString, nullable=True)
    )

    @property
    def is_superuser(self) -> bool:
        """Backwards-compatible alias: admins are superusers."""
        return self.role == "admin"


class UserBase(SQLModel):
    """Base schema for user payloads."""

    name: str


class UserCreate(UserBase):
    """Schema for creating a user."""

    password: str  # Klartext beim Eingang – wird gehasht gespeichert
    role: str = "user"


class UserRead(UserBase):
    """Schema for reading a user."""

    id: int
    is_active: bool
    role: str
    disclaimer_accepted_at: Optional[datetime] = None
    ui_language: Optional[str] = None


class UserLogin(SQLModel):
    """Schema for login credentials."""

    name: str
    password: str


class UserUpdate(SQLModel):
    """Schema for updating a user."""

    name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None


class UiLanguageRead(SQLModel):
    """Schema for reading the current user's UI language."""

    ui_language: Optional[str] = None


class UiLanguageUpdate(SQLModel):
    """Schema for updating the current user's UI language."""

    ui_language: str
