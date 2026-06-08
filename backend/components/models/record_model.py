"""
  openDox - Medical transcription platform
  Copyright (C) 2025  crizz <christopher.abanilla@gmx.de>

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

from sqlmodel import Field, SQLModel
from typing import Optional
from pydantic import BaseModel


class Record(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    user_id: int
    category_id: Optional[int] = Field(default=None, foreign_key="categories.id")
    title: str = Field()
    content: str = Field()
    timestamp: str = Field()
    summarize: str = Field()
    file: str = Field()
    archived: bool = Field(default=False)
    task_id: Optional[int] = Field(default=None, foreign_key="task.id")
    
    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "category_id": self.category_id,
            "title": self.title,
            "content": self.content,
            "timestamp": self.timestamp,
            "summarize": self.summarize,
            "file": self.file,
            "archived": self.archived,
            "task_id": self.task_id,
        }


class RecordBase(SQLModel):
    title: str


class RecordCreate(SQLModel):
    user_id: int
    title: str
    category_id: Optional[int] = None


class RecordUpdate(SQLModel):
    title: Optional[str] = None
    content: Optional[str] = None
    file: Optional[str] = None
    summarize: Optional[str] = None
    category_id: Optional[int] = None


class RecordRead(RecordBase):
    id: int
    session_id: str
    user_id: int
    category_id: Optional[int] = None
    title: str
    content: str
    summarize: Optional[str] = ""
    timestamp: str
    file: str
    archived: bool = False
    task_id: Optional[int] = None


class RecordChunk(BaseModel):
    session_id: str
    user_id: int


class FinalizeRecord(BaseModel):
    session_id: str
    user_id: int