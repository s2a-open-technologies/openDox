"""openDox - Medical transcription platform
Copyright (C) 2026  S2A Open Technologies gGmbH
SPDX-FileCopyrightText: 2026 S2A Open Technologies gGmbH
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
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class AuditEvent(SQLModel, table=True):
    """One entry of the admin audit log (append-only).

    Records privileged actions (settings, users, backups, retries) and security
    events (failed logins, denied requests) — never transcript content, record
    titles, passwords or credential values. ``details`` only ever carries ids,
    field names and short reason codes.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), index=True
    )
    # Snapshot of the actor: the entry stays readable after the user is
    # deleted or renamed. NULL id = anonymous (failed login) or the system.
    actor_user_id: Optional[int] = Field(default=None, index=True)
    actor_name: Optional[str] = None
    actor_role: Optional[str] = None
    action: str = Field(index=True)
    outcome: str = Field(default="success")
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    ip: Optional[str] = None
    details: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))


class AuditEventRead(SQLModel):
    """API shape of an audit entry."""

    id: int
    timestamp: datetime
    actor_user_id: Optional[int]
    actor_name: Optional[str]
    actor_role: Optional[str]
    action: str
    outcome: str
    target_type: Optional[str]
    target_id: Optional[str]
    ip: Optional[str]
    details: Optional[dict[str, Any]]


class AuditEventPage(SQLModel):
    """One page of audit entries plus the total match count."""

    items: list[AuditEventRead]
    total: int
