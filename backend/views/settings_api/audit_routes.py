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

# Standard library
import csv
import io
import json
from datetime import datetime, timezone

# Third-party
from fastapi import Depends, Query, Request, Response
from sqlalchemy import func
from sqlmodel import select

# Custom
from backend.components.models.audit_model import AuditEventPage, AuditEventRead
from backend.components.models.user_model import User
from backend.components.services.audit_service import audit, query_events
from backend.components.sql.sql_engine import SessionDep
from backend.views.settings_api import settings_bp
from backend.views.settings_api.settings_routes import _require_admin

# Upper bound for one CSV export, so a huge log cannot exhaust memory.
EXPORT_MAX_ROWS = 100_000

_CSV_COLUMNS = (
    "timestamp",
    "actor_name",
    "actor_role",
    "action",
    "outcome",
    "target_type",
    "target_id",
    "ip",
    "details",
)


def _csv_cell(value: str) -> str:
    """Defuse spreadsheet formulas: failed-login names are typed by anyone."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def _filters(
    since: datetime | None = None,
    until: datetime | None = None,
    actor: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
) -> dict:
    return {
        "since": since,
        "until": until,
        "actor": actor,
        "action": action,
        "outcome": outcome,
    }


@settings_bp.get("/audit/", response_model=AuditEventPage)
async def list_audit_events(
    db: SessionDep,
    filters: dict = Depends(_filters),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    _: User = Depends(_require_admin),
):
    """Return one page of audit entries, newest first (admin only).

    Reading the log is not logged itself; exporting it is.
    """
    stmt = query_events(**filters)
    total = db.exec(select(func.count()).select_from(stmt.subquery())).one()
    rows = db.exec(stmt.offset(offset).limit(limit)).all()
    return AuditEventPage(
        items=[AuditEventRead.model_validate(r, from_attributes=True) for r in rows],
        total=total,
    )


@settings_bp.get("/audit/export/")
async def export_audit_events(
    request: Request,
    db: SessionDep,
    filters: dict = Depends(_filters),
    admin: User = Depends(_require_admin),
):
    """Download the filtered audit entries as CSV (admin only, logged)."""
    audit(
        db,
        "audit.export",
        request=request,
        actor=admin,
        details={k: str(v) for k, v in filters.items() if v is not None},
        commit=True,
    )
    rows = db.exec(query_events(**filters).limit(EXPORT_MAX_ROWS)).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(_CSV_COLUMNS)
    for row in rows:
        writer.writerow(
            _csv_cell(cell)
            for cell in [
                row.timestamp.isoformat(),
                row.actor_name or "",
                row.actor_role or "",
                row.action,
                row.outcome,
                row.target_type or "",
                row.target_id or "",
                row.ip or "",
                json.dumps(row.details, ensure_ascii=False) if row.details else "",
            ]
        )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        # BOM so Excel opens the UTF-8 file with umlauts intact.
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="opendox-audit-{stamp}.csv"'
        },
    )
