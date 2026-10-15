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


Cross-instance mutual exclusion for startup work, via PostgreSQL advisory locks.

With several app instances starting at once, work that must run exactly once
(re-encrypting data after an ``ENCRYPTION_KEY`` rotation) takes this lock; the
others wait and then find nothing left to do. Other databases (the SQLite
fallback) mean a single instance, so the lock is a no-op there.
"""

import contextlib

from sqlalchemy import text

from backend.components.sql import sql_engine

# Keys are arbitrary constants shared by all instances. alembic/env.py uses
# 7243189005 for migrations.
KEY_ROTATION_LOCK = 7243189006


@contextlib.contextmanager
def advisory_lock(key: int, engine=None):
    """Hold a session-level PostgreSQL advisory lock while the body runs.

    Args:
        key: Lock number; instances contending for the same work use the same.
        engine: SQLAlchemy engine; defaults to the application's.
    """
    engine = engine or sql_engine.engine
    if engine.dialect.name != "postgresql":
        yield
        return
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": key})
        connection.commit()  # the lock belongs to the session, not the transaction
        try:
            yield
        finally:
            connection.rollback()
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
            connection.commit()
