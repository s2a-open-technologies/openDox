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

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status

from backend.components.modules.logger import get_logger
from backend.components.services.redis_client import get_redis

logger = get_logger(__name__)

_MAX_REQUESTS = 5
_WINDOW_SECONDS = 60


class _RateLimiter:
    """Rate limiter keyed by client IP.

    With ``REDIS_URL`` set the counter lives in Redis (fixed window), so the
    limit holds across all app instances instead of multiplying with their
    number. Without Redis, or while Redis is unreachable, it falls back to an
    in-memory sliding window per process. Thread-safe.  In-memory entries older
    than *window_seconds* are lazily evicted on every check so the store cannot
    grow without bound.
    """

    def __init__(
        self,
        max_requests: int = _MAX_REQUESTS,
        window_seconds: int = _WINDOW_SECONDS,
        name: str = "login",
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.name = name
        self._store: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _client_ip(self, request: Request) -> str:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _redis_attempts(self, ip: str) -> int | None:
        """Count this attempt in Redis; ``None`` if Redis is not usable."""
        redis = get_redis()
        if redis is None:
            return None
        key = f"opendox:ratelimit:{self.name}:{ip}"
        try:
            pipe = redis.pipeline()
            # SET NX first so the key always carries an expiry, even if this
            # process dies right after: a counter without TTL would lock the IP
            # out for good.
            pipe.set(key, 0, ex=self.window_seconds, nx=True)
            pipe.incr(key)
            return int(pipe.execute()[1])
        except Exception as exc:
            logger.warning("Rate limiter: Redis unavailable (%s), using memory", exc)
            return None

    def _too_many(self) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )

    def check(self, request: Request) -> None:
        """Raise HTTP 429 if the client has exceeded the rate limit."""
        ip = self._client_ip(request)
        attempts = self._redis_attempts(ip)
        if attempts is not None:
            if attempts > self.max_requests:
                raise self._too_many()
            return
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            timestamps = self._store[ip]
            self._store[ip] = timestamps = [t for t in timestamps if t > cutoff]
            if len(timestamps) >= self.max_requests:
                raise self._too_many()
            timestamps.append(now)


login_limiter = _RateLimiter()
