"""State shared between several app instances: leader lock and rate limit."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from backend.components.services import leader_lock, rate_limiter
from backend.components.services.rate_limiter import _RateLimiter
from tests.fake_redis import FakeRedis


@pytest.fixture
def redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(leader_lock, "get_redis", lambda: fake)
    monkeypatch.setattr(rate_limiter, "get_redis", lambda: fake)
    return fake


def _request(ip="1.2.3.4"):
    request = MagicMock()
    request.client.host = ip
    request.headers = {}
    return request


# --- leader lock -----------------------------------------------------------


def test_without_redis_every_run_is_allowed(monkeypatch):
    monkeypatch.setattr(leader_lock, "get_redis", lambda: None)
    assert leader_lock.try_acquire("job", 60) is True
    assert leader_lock.try_acquire("job", 60) is True


def test_only_one_instance_wins_a_tick(redis):
    assert leader_lock.try_acquire("job", 60) is True  # instance A
    assert leader_lock.try_acquire("job", 60) is False  # instance B, same tick


def test_lock_expires_so_the_next_tick_can_be_won(redis):
    assert leader_lock.try_acquire("job", 60) is True
    redis.advance(61)
    assert leader_lock.try_acquire("job", 60) is True


def test_jobs_are_locked_independently(redis):
    assert leader_lock.try_acquire("a", 60) is True
    assert leader_lock.try_acquire("b", 60) is True


def test_unreachable_redis_still_runs_the_job(redis):
    redis.fail = True
    assert leader_lock.try_acquire("job", 60) is True


# --- rate limiter shared through Redis ------------------------------------


def test_limit_is_shared_between_two_instances(redis):
    a = _RateLimiter(max_requests=3, window_seconds=60)
    b = _RateLimiter(max_requests=3, window_seconds=60)
    a.check(_request())
    b.check(_request())
    a.check(_request())
    with pytest.raises(HTTPException) as exc:
        b.check(_request())  # 4th attempt overall, on the other instance
    assert exc.value.status_code == 429


def test_redis_window_expires(redis):
    limiter = _RateLimiter(max_requests=1, window_seconds=60)
    limiter.check(_request())
    with pytest.raises(HTTPException):
        limiter.check(_request())
    redis.advance(61)
    limiter.check(_request())


def test_redis_limit_is_per_ip(redis):
    limiter = _RateLimiter(max_requests=1, window_seconds=60)
    limiter.check(_request("1.1.1.1"))
    limiter.check(_request("2.2.2.2"))


def test_key_always_has_an_expiry(redis):
    """A crash between the two commands must never leave a permanent lockout."""
    limiter = _RateLimiter(max_requests=5, window_seconds=60)
    limiter.check(_request())
    assert redis.ttl("opendox:ratelimit:login:1.2.3.4") > 0


def test_redis_outage_falls_back_to_process_memory(redis):
    redis.fail = True
    limiter = _RateLimiter(max_requests=2, window_seconds=60)
    limiter.check(_request())
    limiter.check(_request())
    with pytest.raises(HTTPException):
        limiter.check(_request())
