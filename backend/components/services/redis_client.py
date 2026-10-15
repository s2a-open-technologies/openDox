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

Shared Redis client for state that must be visible to every app instance
(rate limits, leader locks). Returns ``None`` without ``REDIS_URL``: the app
then runs as a single instance and keeps that state in process memory.
"""

from typing import Any, Optional

from backend.components.modules.env import env_or_file
from backend.components.modules.logger import get_logger

logger = get_logger(__name__)

_client: Optional[Any] = None
_client_url: Optional[str] = None


def get_redis() -> Optional[Any]:
    """Return a shared ``redis.Redis`` client, or ``None`` if Redis is not set up.

    Short socket timeouts keep a dead Redis from stalling login requests;
    callers must treat any exception as "Redis unavailable" and degrade.
    """
    global _client, _client_url
    url = env_or_file("REDIS_URL")
    if not url:
        return None
    if _client is None or _client_url != url:
        import redis

        _client = redis.from_url(
            url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2
        )
        _client_url = url
        logger.info("Shared Redis client created")
    return _client
