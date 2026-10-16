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

from typing import Optional

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from backend.components.security.field_encryption import EncryptedString


class LdapSettingsModel(SQLModel, table=True):
    """LDAP authentication settings singleton model."""

    id: Optional[int] = Field(default=None, primary_key=True)
    server_host: str
    server_port: int
    use_ssl: bool = False
    base_dn: str
    user_dn: str
    search_filter: Optional[str] = Field(default=None)
    bind_user_dn: Optional[str] = None
    bind_user_password: Optional[str] = Field(
        default=None, sa_column=Column(EncryptedString, nullable=True)
    )
    cert_filename: Optional[str] = None
    cert_data: Optional[str] = None
    nested_groups: bool = False
    allowed_groups: Optional[str] = None
    admin_groups: Optional[str] = None
    moderator_groups: Optional[str] = None
