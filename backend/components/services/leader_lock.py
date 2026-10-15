"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-FileCopyrightText: 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
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

"Only one instance runs this tick" for periodic jobs.

With several app instances every instance starts the same background loops
(stale-session cleanup, archival, ...). Each loop asks :func:`try_acquire`
before a run; the first instance wins and the lock expires on its own, so a
crashed winner never blocks the job for longer than ``ttl_s``.
"""

import uuid

from backend.components.modules.logger import get_logger
from backend.components.services.redis_client import get_redis

logger = get_logger(__name__)

_INSTANCE_ID = uuid.uuid4().hex


def try_acquire(name: str, ttl_s: int) -> bool:
    """Try to become the one instance that runs job ``name`` for the next ``ttl_s``.

    Args:
        name: Job name, shared by all instances.
        ttl_s: How long the claim lasts. Use a bit less than the loop interval so
            the next tick can be won again.

    Returns:
        True if this instance should run the job. Always True without Redis
        (single instance) and, deliberately, when Redis is unreachable: the jobs
        are idempotent, so running twice is better than not running at all.
    """
    redis = get_redis()
    if redis is None:
        return True
    try:
        return bool(
            redis.set(f"opendox:lock:{name}", _INSTANCE_ID, nx=True, ex=int(ttl_s))
        )
    except Exception as exc:
        logger.warning("Leader lock %r unavailable (%s), running anyway", name, exc)
        return True
