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
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from backend.components.services.rate_limiter import _RateLimiter


class TestRateLimiter:
    def test_allows_requests_within_limit(self):
        limiter = _RateLimiter(max_requests=3, window_seconds=60)
        request = MagicMock()
        request.client.host = "1.2.3.4"
        request.headers = {}
        for _ in range(3):
            limiter.check(request)

    def test_blocks_requests_exceeding_limit(self):
        limiter = _RateLimiter(max_requests=3, window_seconds=60)
        request = MagicMock()
        request.client.host = "1.2.3.4"
        request.headers = {}
        for _ in range(3):
            limiter.check(request)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check(request)
        assert exc_info.value.status_code == 429
        assert "Too many" in exc_info.value.detail

    def test_tracks_ips_independently(self):
        limiter = _RateLimiter(max_requests=2, window_seconds=60)
        request_a = MagicMock()
        request_a.client.host = "1.1.1.1"
        request_a.headers = {}
        request_b = MagicMock()
        request_b.client.host = "2.2.2.2"
        request_b.headers = {}
        for _ in range(2):
            limiter.check(request_a)
        limiter.check(request_b)
        with pytest.raises(HTTPException):
            limiter.check(request_a)

    def test_window_expiry_allows_new_requests(self):
        limiter = _RateLimiter(max_requests=2, window_seconds=1)
        request = MagicMock()
        request.client.host = "1.2.3.4"
        request.headers = {}
        limiter.check(request)
        limiter.check(request)
        time.sleep(1.1)
        limiter.check(request)

    def test_x_forwarded_for_takes_priority(self):
        limiter = _RateLimiter(max_requests=1, window_seconds=60)
        request = MagicMock()
        request.client.host = "10.0.0.1"
        request.headers = {"x-forwarded-for": "5.6.7.8, 9.10.11.12"}
        limiter.check(request)
        with pytest.raises(HTTPException):
            limiter.check(request)

    def test_different_xff_ips_tracked_separately(self):
        limiter = _RateLimiter(max_requests=1, window_seconds=60)
        request_a = MagicMock()
        request_a.client.host = "10.0.0.1"
        request_a.headers = {"x-forwarded-for": "1.1.1.1"}
        request_b = MagicMock()
        request_b.client.host = "10.0.0.1"
        request_b.headers = {"x-forwarded-for": "2.2.2.2"}
        limiter.check(request_a)
        limiter.check(request_b)

    def test_no_client_ip_uses_unknown(self):
        limiter = _RateLimiter(max_requests=1, window_seconds=60)
        request = MagicMock()
        request.client = None
        request.headers = {}
        limiter.check(request)
        with pytest.raises(HTTPException):
            limiter.check(request)

    def test_thread_safety(self):
        import concurrent.futures

        limiter = _RateLimiter(max_requests=100, window_seconds=60)
        request = MagicMock()
        request.client.host = "1.2.3.4"
        request.headers = {}
        errors = []

        def check():
            try:
                limiter.check(request)
            except HTTPException:
                errors.append(True)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            list(pool.map(lambda _: check(), range(200)))
        assert len(errors) == 100


class TestLoginRateLimitIntegration:
    def test_login_returns_429_after_max_attempts(self, client, session_factory):
        from backend.components.services.rate_limiter import login_limiter

        original_max = login_limiter.max_requests
        original_window = login_limiter.window_seconds
        login_limiter.max_requests = 3
        login_limiter.window_seconds = 60
        login_limiter._store.clear()
        try:
            payload = {"name": "ratelimituser", "password": "wrong"}
            for _ in range(3):
                resp = client.post("/api/v1/auth/login", json=payload)
                assert resp.status_code in (401, 422)
            resp = client.post("/api/v1/auth/login", json=payload)
            assert resp.status_code == 429
            assert "Too many" in resp.json()["detail"]
        finally:
            login_limiter.max_requests = original_max
            login_limiter.window_seconds = original_window
            login_limiter._store.clear()

    def test_login_rate_limit_per_ip(self, client, session_factory):
        from backend.components.services.rate_limiter import login_limiter

        original_max = login_limiter.max_requests
        original_window = login_limiter.window_seconds
        login_limiter.max_requests = 2
        login_limiter.window_seconds = 60
        login_limiter._store.clear()
        try:
            payload = {"name": "ratelimituser", "password": "wrong"}
            client.post("/api/v1/auth/login", json=payload)
            client.post("/api/v1/auth/login", json=payload)
            resp = client.post(
                "/api/v1/auth/login",
                json=payload,
                headers={"x-forwarded-for": "different-ip"},
            )
            assert resp.status_code in (401, 422)
        finally:
            login_limiter.max_requests = original_max
            login_limiter.window_seconds = original_window
            login_limiter._store.clear()
