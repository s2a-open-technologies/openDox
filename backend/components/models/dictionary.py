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

from datetime import datetime, timezone
from typing import Literal, Optional

from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel

from backend.components.security.field_encryption import EncryptedString


def _utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Dictionary(SQLModel, table=True):
    """Term list for the phonetic term correction.

    ``user_id`` None = global (admin/moderator-managed, attachable to global
    categories); set = personal, visible to its owner only (never to admins,
    unlike personal categories). A dictionary only takes effect through the
    categories it is attached to (``CategoryDictionaryLink``).
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    user_id: Optional[int] = Field(default=None, index=True)
    # One term per line. Encrypted at rest: users realistically enter
    # patient/doctor names in personal dictionaries.
    terms: str = Field(default="", sa_column=Column(EncryptedString, nullable=False))
    term_count: int = Field(default=0)
    updated_at: datetime = Field(default_factory=_utcnow)


class CategoryDictionaryLink(SQLModel, table=True):
    """Attaches a dictionary to a category (many-to-many)."""

    category_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("categories.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    dictionary_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("dictionary.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )


class DictionaryCreate(SQLModel):
    """Schema for creating a dictionary."""

    name: str
    scope: Literal["global", "personal"] = "personal"
    terms: Optional[list[str]] = None


class DictionaryUpdate(SQLModel):
    """Schema for renaming a dictionary and/or replacing its terms."""

    name: Optional[str] = None
    terms: Optional[list[str]] = None


class DictionaryListRead(SQLModel):
    """List shape — without the (possibly very long) term list."""

    id: int
    name: str
    user_id: Optional[int] = None
    term_count: int
    updated_at: datetime
    category_ids: list[int] = []


class DictionaryRead(DictionaryListRead):
    """Single dictionary including its terms."""

    terms: list[str] = []
