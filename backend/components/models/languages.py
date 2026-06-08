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

class LanguagesBase(SQLModel):
    name: str = Field(index=True)
    country_code: str
    system_prompt: str

class Languages(LanguagesBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class LanguagesCreate(LanguagesBase):
    pass 

class LanguagesRead(LanguagesBase):
    id: int