"""
  openDox - Medical transcription platform
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

from typing import Optional
from sqlmodel import Field, SQLModel

class LdapSettingsModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    server_host: str
    server_port: int
    use_ssl: bool = False
    base_dn: str
    user_dn: str
    bind_user_dn: Optional[str] = None
    bind_user_password: Optional[str] = None
    cert_filename: Optional[str] = None
