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
"""

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status

_MAX_REQUESTS = 5
_WINDOW_SECONDS = 60


class _RateLimiter:
    """In-memory sliding-window rate limiter keyed by client IP.

    Thread-safe.  Entries older than *window_seconds* are lazily evicted on
    every check so the store cannot grow without bound.
    """

    def __init__(
        self,
        max_requests: int = _MAX_REQUESTS,
        window_seconds: int = _WINDOW_SECONDS,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._store: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _client_ip(self, request: Request) -> str:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def check(self, request: Request) -> None:
        """Raise HTTP 429 if the client has exceeded the rate limit."""
        ip = self._client_ip(request)
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            timestamps = self._store[ip]
            self._store[ip] = timestamps = [t for t in timestamps if t > cutoff]
            if len(timestamps) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many login attempts. Please try again later.",
                )
            timestamps.append(now)


login_limiter = _RateLimiter()
