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

from typing import Optional
from sqlmodel import Field, SQLModel

from typing import Optional
from sqlmodel import Field, SQLModel, Relationship

class TerminologyBase(SQLModel):
    code: str = Field(index=True, unique=True)  # z.B. "S82.9"
    type: str = Field(index=True)               # "ICD", "OPS" oder "USER"
    official_text: str                          # Der Text aus dem Katalog
    custom_alias: Optional[str] = None          # Dein "Textbaustein" (z.B. "Fraktur rechtes Bein")
    is_protected: bool = Field(default=True)    # Flag für das LLM: "Nicht verändern!"
    year: int = Field(default=2026) 

class Terminology(TerminologyBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class TerminologyRead(TerminologyBase):
    id: int

class TerminologyCreate(TerminologyBase):
    pass
    