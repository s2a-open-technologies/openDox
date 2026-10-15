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

# Standard library
from datetime import datetime

# Third-party
from sqlmodel import select

# Custom
from backend.components.models.record_model import Record
from backend.components.modules.logger import get_logger
from backend.components.services.settings_service import get_audio_settings
from backend.components.sql.sql_engine import get_session_factory

logger = get_logger(__name__)
session_factory = get_session_factory()

_RECORD_TIMESTAMP_FORMAT = "%d.%m.%Y %H:%M:%S"


def _parse_record_timestamp(raw: str) -> datetime | None:
    """Parse a Record.timestamp into a datetime, or None when unparsable.

    Records carry a German display timestamp (``DD.MM.YYYY HH:MM[:SS]``,
    zero-padded as written by ``datetime.now().strftime(..., "%d.%m.%Y")``),
    not a DB datetime column — the same format
    ``frontend/src/lib/archive.ts`` already parses. Optimistic frontend
    entries (``toLocaleString("de-DE")``) lack zero padding, hence a
    whitespace/comma-tolerant strict-format pass first and a plain parse
    fallback second.
    """
    text = (raw or "").strip()
    if not text:
        return None

    normalized = text.replace(",", " ")
    parts = normalized.replace(":", " ").replace(".", " ").split()
    try:
        if len(parts) == 5:
            day, month, year, hour, minute = (int(p) for p in parts)
            return datetime(year, month, day, hour, minute)
        if len(parts) == 6:
            day, month, year, hour, minute, second = (int(p) for p in parts)
            return datetime(year, month, day, hour, minute, second)
    except ValueError:
        pass

    try:
        return datetime.strptime(normalized, _RECORD_TIMESTAMP_FORMAT)
    except ValueError:
        logger.warning(f"Unparsable record timestamp, skipping: {raw!r}")
        return None


def auto_archive_old_records(now: datetime | None = None) -> int:
    """Set ``archived = True`` on every record older than the configured age.

    Daily housekeeping for the admin-configurable auto-archiving
    (``AudioSettingsModel.auto_archive_enabled``/``auto_archive_days``, see
    the Audio tab in the admin UI). Same effect as a user clicking
    "Archivieren" in the row menu, just time-driven: ``Record.archived``
    flips to True and the recording moves to the archive tab; no content is
    modified and unarchiving stays possible at any time — a later run won't
    touch it again until it would newly cross the threshold (archived
    records are excluded from the query).

    Zero-failure-by-design: each record commits in its own session, any
    error is logged and the loop continues with the rest.

    Args:
        now: Override the current time (tests only).

    Returns:
        Number of records archived during this run.
    """
    audio_settings = get_audio_settings()
    if not audio_settings.auto_archive_enabled:
        return 0

    age_days = audio_settings.auto_archive_days
    if age_days <= 0:
        return 0

    now = now or datetime.now()
    archived = 0
    db = session_factory()
    try:
        records = db.exec(select(Record).where(Record.archived == False)).all()  # noqa: E712
    except Exception as e:
        logger.warning(f"Auto-archive query failed: {e}")
        db.close()
        return 0
    finally:
        pass

    ids = [record.id for record in records]
    db.close()

    for record_id in ids:
        session = session_factory()
        try:
            record = session.get(Record, record_id)
            if record is None or record.archived:
                continue
            stamp = _parse_record_timestamp(record.timestamp)
            if stamp is None:
                continue
            age = (now - stamp).total_seconds() / 86_400
            if age < age_days:
                continue
            record.archived = True
            session.add(record)
            session.commit()
            archived += 1
            logger.info(
                f"[RECORD {record_id}] Auto-archived (age {age:.1f}d >= {age_days}d)"
            )
        except Exception as e:
            session.rollback()
            logger.warning(f"[RECORD {record_id}] Auto-archive failed: {e}")
        finally:
            session.close()

    return archived
