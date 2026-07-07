"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

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


class User(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, default=None)
    name: str = Field(index=True, unique=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    disclaimer_accepted_at: Optional[datetime] = Field(default=None)


class UserBase(SQLModel):
    name: str


class UserCreate(UserBase):
    password: str  # Klartext beim Eingang – wird gehasht gespeichert
    is_superuser: bool = False


class UserRead(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    disclaimer_accepted_at: Optional[datetime] = None


class UserLogin(SQLModel):
    name: str
    password: str


class UserUpdate(SQLModel):
    name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
