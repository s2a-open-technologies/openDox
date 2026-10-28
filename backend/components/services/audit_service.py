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

Admin audit log: privileged actions and security events.

What goes in is deliberately narrow (see AGENTS.md, "Audit Log"): settings,
user management, backups, failed-task retries, failed logins, denied requests
and role changes by the directory group sync. Users working with their own
records are never logged. Entries never carry transcript content, record
titles, passwords or credential values — settings changes are logged as the
list of changed field *names*.
"""

# Standard library
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

# Third-party
from fastapi import FastAPI, Request
from sqlmodel import Session, delete, select

# Custom
from backend.components.models.audit_model import AuditEvent
from backend.components.models.user_model import User
from backend.components.modules.logger import get_logger
from backend.components.security.hashing import decode_token

logger = get_logger(__name__)

# Login and OIDC callback log their own, more specific failure events.
_DENIED_SKIP_SUFFIXES = ("/auth/login", "/auth/oidc/callback")


def client_ip(request: Request | None) -> str | None:
    """Return the caller's IP, honouring X-Forwarded-For only behind a trusted proxy.

    ``request.state.trusted_proxy`` is set by ``run.py``'s ``mark_trusted_proxy``
    middleware; without it (tests, direct access) the header is ignored, since
    anyone could otherwise write an arbitrary address into the log.
    """
    if request is None:
        return None
    if getattr(request.state, "trusted_proxy", False):
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return request.client.host if request.client else None


def audit(
    db: Session,
    action: str,
    *,
    request: Request | None = None,
    actor: User | None = None,
    actor_name: str | None = None,
    outcome: str = "success",
    target_type: str | None = None,
    target_id: Any = None,
    details: dict[str, Any] | None = None,
    commit: bool = False,
) -> None:
    """Add an audit entry to ``db``.

    By default the entry is only added, so it is committed together with the
    change it describes (or rolled back with it). Pass ``commit=True`` for
    events without a change of their own, e.g. a failed login.

    Args:
        db: Active database session.
        action: Dotted action code, e.g. ``settings.llm.update``.
        request: Current request, for the caller's IP.
        actor: User who acted; ``None`` = anonymous or the system.
        actor_name: Name to record when there is no ``actor`` (failed login).
        outcome: ``success``, ``failure`` or ``denied``.
        target_type: Kind of object acted on (``user``, ``category`` ...).
        target_id: Id of that object.
        details: Ids, field names, reason codes — never content or secrets.
        commit: Commit right away.
    """
    db.add(
        AuditEvent(
            actor_user_id=actor.id if actor else None,
            actor_name=actor.name if actor else actor_name,
            actor_role=actor.role if actor else None,
            action=action,
            outcome=outcome,
            target_type=target_type,
            target_id=None if target_id is None else str(target_id),
            ip=client_ip(request),
            details=details,
        )
    )
    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Could not write audit event %s", action)


def snapshot(row) -> dict[str, Any]:
    """Return a row's field values for :func:`changed_fields` (``{}`` for None)."""
    return row.model_dump() if row is not None else {}


def changed_fields(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Return the sorted names of the fields whose value differs (without ``id``)."""
    keys = (set(before) | set(after)) - {"id"}
    return sorted(k for k in keys if before.get(k) != after.get(k))


def _user_from_bearer(db: Session, request: Request) -> User | None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        payload = decode_token(token) or {}
        return db.get(User, int(payload.get("sub")))
    except Exception:
        return None


def _log_denied(session_factory: Callable[[], Session], request: Request) -> None:
    with session_factory() as db:
        audit(
            db,
            "access.denied",
            request=request,
            actor=_user_from_bearer(db, request),
            outcome="denied",
            details={"method": request.method, "path": request.url.path},
            commit=True,
        )


def add_denied_access_middleware(
    app: FastAPI, session_factory: Callable[[], Session]
) -> None:
    """Log every 403 response of an API route as an ``access.denied`` event.

    One place instead of every guard (``_require_admin``, ``_require_owner``,
    the category/dictionary ownership checks ...). Fail-open: a logging error
    never changes the response.
    """

    @app.middleware("http")
    async def log_denied_access(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if (
            response.status_code == 403
            and "/api/" in path
            and not path.endswith(_DENIED_SKIP_SUFFIXES)
        ):
            try:
                await asyncio.to_thread(_log_denied, session_factory, request)
            except Exception:
                logger.exception("Could not write access.denied audit event")
        return response


def purge_expired(session_factory: Callable[[], Session], retention_days: int) -> int:
    """Delete audit entries older than ``retention_days``; 0 days keeps everything.

    Returns:
        Number of deleted entries.
    """
    if retention_days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    with session_factory() as db:
        result = db.exec(delete(AuditEvent).where(AuditEvent.timestamp < cutoff))
        db.commit()
        return result.rowcount or 0


def query_events(
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    actor: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
):
    """Build the filtered, newest-first select for the audit view and export."""
    stmt = select(AuditEvent)
    if since is not None:
        stmt = stmt.where(AuditEvent.timestamp >= since)
    if until is not None:
        stmt = stmt.where(AuditEvent.timestamp <= until)
    if actor:
        stmt = stmt.where(AuditEvent.actor_name.ilike(f"%{actor}%"))
    if action:
        stmt = stmt.where(AuditEvent.action.startswith(action))
    if outcome:
        stmt = stmt.where(AuditEvent.outcome == outcome)
    return stmt.order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
