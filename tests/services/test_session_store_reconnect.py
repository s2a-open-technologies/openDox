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

"""Tests for the session store's Redis-reconnect path.

Covers the runtime race where the app process starts while Redis is still
down (``depends_on: service_healthy`` only orders initial ``compose up``
creation, not single-container restarts) and the in-memory fallback would
otherwise be permanent until the next full restart.
"""

from types import SimpleNamespace

import backend.components.services.session_store as session_store_module
from backend.components.services.session_store import (
    SessionStore,
    reconnect_session_store,
)


class _FakeRedisStore:
    """Minimal RedisSessionStore stand-in: has ping(), fails until told not to."""

    def __init__(self, fail_ping: bool = False):
        self.fail_ping = fail_ping

    def ping(self):
        if self.fail_ping:
            raise ConnectionError("redis down")
        return True


def _restore(monkeypatch, original_store):
    """Put the module back into its original state after a test."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    session_store_module.session_store.set(original_store)


def test_reconnect_is_noop_without_redis_url(monkeypatch):
    """No REDIS_URL configured → reconnect returns False and keeps the store."""
    original = session_store_module.session_store.get()
    monkeypatch.delenv("REDIS_URL", raising=False)

    assert reconnect_session_store() is False
    assert session_store_module.session_store.get() is original


def test_reconnect_fails_cleanly_when_redis_unreachable(monkeypatch):
    """REDIS_URL set but Redis down → False, in-memory store stays active."""
    original = session_store_module.session_store.get()
    monkeypatch.setenv("REDIS_URL", "redis://localhost:59999/0")

    fake = SimpleNamespace(ping=lambda: (_ for _ in ()).throw(ConnectionError()))
    module = session_store_module
    # Force the "current store is redis-like but unreachable" branch off by
    # keeping an in-memory store; the reconnect then tries a real connection
    # which fails against a dead port.
    module.session_store.set(SessionStore())
    monkeypatch.setattr(
        "backend.components.services.session_store_redis.RedisSessionStore",
        lambda url: fake,
    )

    assert reconnect_session_store() is False
    module.session_store.set(original)


def test_reconnect_swaps_in_redis_store(monkeypatch):
    """Fallback active + Redis reachable → proxy swaps to RedisSessionStore."""
    original = session_store_module.session_store.get()
    monkeypatch.setenv("REDIS_URL", "redis://localhost:56379/0")

    created = []

    def fake_factory(url):
        store = _FakeRedisStore()
        created.append(url)
        return store

    monkeypatch.setattr(
        "backend.components.services.session_store_redis.RedisSessionStore",
        fake_factory,
    )

    assert reconnect_session_store() is True
    assert created and created[0] == "redis://localhost:56379/0"
    assert isinstance(session_store_module.session_store.get(), _FakeRedisStore)
    # Proxy still forwards attribute access to the swapped store.
    assert session_store_module.session_store.ping() is True

    _restore(monkeypatch, original)


def test_reconnect_keeps_existing_healthy_redis_store(monkeypatch):
    """Already Redis-backed and reachable → no rebuild, returns True."""
    original = session_store_module.session_store.get()
    monkeypatch.setenv("REDIS_URL", "redis://localhost:56379/0")

    healthy = _FakeRedisStore()
    created = []

    def fake_factory(url):
        created.append(url)
        return _FakeRedisStore()

    session_store_module.session_store.set(healthy)
    monkeypatch.setattr(
        "backend.components.services.session_store_redis.RedisSessionStore",
        fake_factory,
    )

    assert reconnect_session_store() is True
    assert not created
    assert session_store_module.session_store.get() is healthy

    _restore(monkeypatch, original)


def test_reconnect_rebuilds_after_healthy_store_degrades(monkeypatch):
    """Existing Redis store unreachable → fresh store is built and swapped."""
    original = session_store_module.session_store.get()
    monkeypatch.setenv("REDIS_URL", "redis://localhost:56379/0")

    broken = _FakeRedisStore(fail_ping=True)
    created = []

    def fake_factory(url):
        created.append(url)
        return _FakeRedisStore()

    session_store_module.session_store.set(broken)
    monkeypatch.setattr(
        "backend.components.services.session_store_redis.RedisSessionStore",
        fake_factory,
    )

    assert reconnect_session_store() is True
    assert created
    assert session_store_module.session_store.get() is not broken

    _restore(monkeypatch, original)


def test_proxy_forwards_attributes_to_active_store():
    """The module-level proxy reads through to the currently active store."""
    proxy = session_store_module.session_store
    inner = proxy.get()
    # Method resolution must be identical (same function object via getattr),
    # `is` fails because getattr creates a fresh bound method each access.
    assert proxy.cleanup_stale_sessions == inner.cleanup_stale_sessions
    assert proxy.cleanup_stale_sessions.__func__ is (
        inner.cleanup_stale_sessions.__func__
    )


def test_health_endpoint_reports_disabled_without_redis_url(
    client, create_user, auth_headers
):
    """services-health: no REDIS_URL → Cache shows 'disabled' (in-memory by design)."""
    from backend.components.modules.env import env_or_file

    if env_or_file("REDIS_URL"):
        # This test is only meaningful when the test env has no Redis config;
        # CI/dev environments without REDIS_URL always hit the disabled branch.
        return
    admin = create_user("admin-health", role="admin")
    response = client.get(
        "/api/v1/settings/services-health/",
        headers=auth_headers(admin),
    )
    assert response.status_code == 200
    services = {s["name"]: s["status"] for s in response.json()["services"]}
    assert services.get("Cache") == "disabled"
