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


Automatic deletion of old records (retention).

The admin sets a maximum retention (``AudioSettingsModel.auto_delete_*``,
Admin UI → Archivierung); every user may choose a shorter one for their own
records (``User.auto_delete_days``, profile → Aufbewahrung). A record is
deleted once it is older than the shorter of the two — archived or not, its
persisted audio included. Runs from ``run.py``'s auto-archive loop.
"""

# Standard library
from datetime import datetime

# Third-party
from sqlmodel import Session, select

# Custom
from backend.components.models.record_model import Record
from backend.components.models.task_model import ACTIVE_TASK_STATUSES, Task
from backend.components.models.user_model import User
from backend.components.modules.logger import get_logger
from backend.components.services import audio_storage
from backend.components.services.audit_service import audit
from backend.components.services.auto_archive_service import _parse_record_timestamp
from backend.components.services.retained_audio import (
    detach_retained_audio,
    remove_retained_audio,
)
from backend.components.services.settings_service import get_audio_settings
from backend.components.sql.sql_engine import get_session_factory

logger = get_logger(__name__)
session_factory = get_session_factory()


def delete_record_with_audio(db: Session, record: Record) -> None:
    """Delete a record and, after the commit, all of its audio.

    Shared by the manual delete route and the retention job. Removes the
    persisted download audio and any audio still retained for a retry of a
    failed transcription. The bytes are only removed once the row is gone,
    so a failed commit never leaves a record pointing at missing audio.
    """
    audio_key = record.file or None
    task = db.get(Task, record.task_id) if record.task_id else None
    retained = detach_retained_audio(task) if task is not None else None
    if retained is not None:
        db.add(task)
    db.delete(record)
    db.commit()
    if audio_key:
        audio_storage.delete(audio_key)
        logger.info(f"[DELETE] Audio object removed: {audio_key}")
    remove_retained_audio(retained)


def effective_retention_days(
    global_days: int | None, personal_days: int | None
) -> int | None:
    """Return the period that applies to a user: the shorter one, None = keep."""
    limits = [d for d in (global_days, personal_days) if d is not None and d > 0]
    return min(limits) if limits else None


def auto_delete_old_records(now: datetime | None = None) -> int:
    """Delete every record older than its owner's effective retention.

    Records whose transcription is still running are skipped. Each record is
    deleted in its own session; an error is logged and the run continues.
    One audit entry per run records how many were deleted (no ids, no titles).

    Args:
        now: Override the current time (tests only).

    Returns:
        Number of records deleted during this run.
    """
    settings = get_audio_settings()
    global_days = settings.auto_delete_days if settings.auto_delete_enabled else None

    db = session_factory()
    try:
        personal = dict(
            db.exec(
                select(User.id, User.auto_delete_days).where(
                    User.auto_delete_days.is_not(None)
                )
            ).all()
        )
        if effective_retention_days(global_days, None) is None and not personal:
            return 0
        candidates = db.exec(
            select(Record.id, Record.user_id, Record.timestamp, Record.task_id)
        ).all()
    except Exception as e:
        logger.warning(f"Auto-delete query failed: {e}")
        return 0
    finally:
        db.close()

    now = now or datetime.now()
    deleted = 0
    for record_id, user_id, timestamp, task_id in candidates:
        limit = effective_retention_days(global_days, personal.get(user_id))
        if limit is None:
            continue
        stamp = _parse_record_timestamp(timestamp)
        if stamp is None or (now - stamp).total_seconds() / 86_400 < limit:
            continue
        session = session_factory()
        try:
            task = session.get(Task, task_id) if task_id else None
            if task is not None and task.status in ACTIVE_TASK_STATUSES:
                continue
            record = session.get(Record, record_id)
            if record is None:
                continue
            delete_record_with_audio(session, record)
            deleted += 1
            logger.info(f"[RECORD {record_id}] Auto-deleted (retention {limit}d)")
        except Exception as e:
            session.rollback()
            logger.warning(f"[RECORD {record_id}] Auto-delete failed: {e}")
        finally:
            session.close()

    if deleted:
        with session_factory() as session:
            audit(
                session,
                "records.auto_delete",
                details={"count": deleted},
                commit=True,
            )
    return deleted
