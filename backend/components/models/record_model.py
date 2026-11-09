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

import json
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from backend.components.security.field_encryption import EncryptedString


class Record(SQLModel, table=True):
    """Record model for transcriptions."""

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    user_id: int
    category_id: Optional[int] = Field(default=None, foreign_key="categories.id")
    title: str = Field(sa_column=Column(EncryptedString, nullable=False, default=""))
    content: str = Field(sa_column=Column(EncryptedString, nullable=False, default=""))
    timestamp: str = Field()
    summarize: str = Field(
        sa_column=Column(EncryptedString, nullable=False, default="")
    )
    file: str = Field()
    archived: bool = Field(default=False)
    task_id: Optional[int] = Field(default=None, foreign_key="task.id")

    pii_mapping: Optional[str] = Field(
        default=None, sa_column=Column(EncryptedString, nullable=True)
    )

    # Dictation in another language (translation_gate). None = dictated in the
    # instance language; then the fields below stay empty. ``content`` always
    # keeps the original, the summary runs on ``translation``.
    source_language: Optional[str] = Field(default=None)
    # Instance language the text was translated into (it may change later).
    translation_language: Optional[str] = Field(default=None)
    translation: Optional[str] = Field(
        default=None, sa_column=Column(EncryptedString, nullable=True)
    )
    # JSON list of translation.translator.Segment dicts (sentence pairs).
    translation_segments: Optional[str] = Field(
        default=None, sa_column=Column(EncryptedString, nullable=True)
    )

    def segments(self) -> list[dict]:
        """Return the stored sentence pairs ([] if none or unreadable)."""
        try:
            data = json.loads(self.translation_segments or "[]")
        except ValueError:
            return []
        return data if isinstance(data, list) else []

    def to_dict(self):
        """Return the record's fields as a plain dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "category_id": self.category_id,
            "title": self.title,
            "content": self.content,
            "timestamp": self.timestamp,
            "summarize": self.summarize,
            "has_audio": bool(self.file),
            "archived": self.archived,
            "task_id": self.task_id,
            "source_language": self.source_language,
            "translation_language": self.translation_language,
            "translation": self.translation or "",
            "translation_segments": self.segments(),
        }


class RecordBase(SQLModel):
    """Base schema for record payloads."""

    title: str


class RecordCreate(SQLModel):
    """Schema for creating a record."""

    user_id: int
    title: str
    category_id: Optional[int] = None
    # Dictation language (ISO 639-1); omitted = the instance language.
    source_language: Optional[str] = None


class SegmentEdit(SQLModel):
    """An edited translated sentence (index into the stored pairs)."""

    index: int
    target: str


class RecordUpdate(SQLModel):
    """Schema for updating a record."""

    title: Optional[str] = None
    content: Optional[str] = None
    summarize: Optional[str] = None
    category_id: Optional[int] = None
    # Edited translated sentences; sources stay, numbers are checked again.
    translation_segments: Optional[list[SegmentEdit]] = None


class RecordRead(RecordBase):
    """Schema for reading a record."""

    id: int
    session_id: str
    user_id: int
    category_id: Optional[int] = None
    title: str
    content: str
    summarize: Optional[str] = ""
    # False → no LLM summary for this record; summarize then carries the
    # transcript (see llm_gate.effective_summary).
    summary_enabled: bool = True
    timestamp: str
    has_audio: bool = False
    archived: bool = False
    task_id: Optional[int] = None
    source_language: Optional[str] = None
    translation_language: Optional[str] = None
    translation: str = ""
    translation_segments: list[dict] = []


class RecordChunk(BaseModel):
    """Schema identifying a live recording session chunk."""

    session_id: str
    user_id: int


class FinalizeRecord(BaseModel):
    """Schema for finalizing a live recording session."""

    session_id: str
    user_id: int
