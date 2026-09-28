"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-FileCopyrightText: 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
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


class User(SQLModel, table=True):
    """User model for authentication and role management."""

    id: Optional[int] = Field(primary_key=True, default=None)
    name: str = Field(index=True, unique=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    role: str = Field(default="user", index=True)
    disclaimer_accepted_at: Optional[datetime] = Field(default=None)
    # Free-text glossary (same comma/semicolon/newline format as
    # Categories.glossary), private to the owner — merged with the
    # selected recording's category glossary at term-correction time. Never
    # exposed via UserRead/any admin-facing user schema, only via the
    # dedicated PersonalGlossaryRead/-Update pair below. Encrypted at rest
    # like the other patient-adjacent fields (Record.content etc.) — users
    # realistically enter patient/doctor names here.
    personal_glossary: Optional[str] = Field(
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


class PersonalGlossaryRead(SQLModel):
    """Schema for reading the current user's personal glossary.

    Deliberately narrow — never composed with UserRead or any
    admin-facing user schema, since the personal glossary is private to
    its owner (see GET/PUT /api/v1/settings/my-dictionary/).
    """

    personal_glossary: Optional[str] = None


class PersonalGlossaryUpdate(SQLModel):
    """Schema for updating the current user's personal glossary."""

    personal_glossary: Optional[str] = None
