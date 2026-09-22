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

from sqlmodel import Field, SQLModel

# Valid role values. ``admin`` supersedes the legacy ``is_superuser=True``.
# ``demo_viewer``: sieht alle Admin-Bereiche, aber nur lesend (Demo-Zwecke);
# einzig Kategorien bleiben für diese Rolle bearbeitbar.
ROLES = ("admin", "moderator", "demo_viewer", "user")


class User(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, default=None)
    name: str = Field(index=True, unique=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    role: str = Field(default="user", index=True)
    disclaimer_accepted_at: Optional[datetime] = Field(default=None)

    @property
    def is_superuser(self) -> bool:
        """Backwards-compatible alias: admins are superusers."""
        return self.role == "admin"


class UserBase(SQLModel):
    name: str


class UserCreate(UserBase):
    password: str  # Klartext beim Eingang – wird gehasht gespeichert
    role: str = "user"


class UserRead(UserBase):
    id: int
    is_active: bool
    role: str
    disclaimer_accepted_at: Optional[datetime] = None


class UserLogin(SQLModel):
    name: str
    password: str


class UserUpdate(SQLModel):
    name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None
