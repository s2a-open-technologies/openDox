"""A session rebuilt after the store was lost must keep the audio already on disk.

If the session store is empty (server restart without Redis, Redis data lost) the
WebSocket handler rebuilds the session from the database record. Creating the
session used to open the PCM file with "wb", which empties it: the whole earlier
part of the recording vanished without any message.
"""

import os
from unittest.mock import MagicMock

import pytest

from backend.components.services import pcm_file, session_store_redis
from backend.components.services.session_store import SessionStore


def _make(tmp_path, name="session_s1.pcm", size=0):
    path = tmp_path / name
    path.write_bytes(b"\x01" * size)
    return str(path)


# --- the helper -------------------------------------------------------------


def test_new_recording_gets_an_empty_file(tmp_path):
    path = str(tmp_path / "session_new.pcm")
    assert pcm_file.open_session_audio(path) == 0
    assert os.path.getsize(path) == 0


def test_existing_audio_is_adopted_not_emptied(tmp_path):
    path = _make(tmp_path, size=64000)
    assert pcm_file.open_session_audio(path) == 64000
    assert os.path.getsize(path) == 64000


def test_half_written_sample_at_the_end_is_trimmed(tmp_path):
    """Float32 PCM must be a multiple of 4 bytes or the WAV conversion fails."""
    path = _make(tmp_path, size=1003)
    assert pcm_file.open_session_audio(path) == 1000
    assert os.path.getsize(path) == 1000


# --- both session stores use it ---------------------------------------------


def test_in_memory_store_adopts_existing_audio(tmp_path):
    path = _make(tmp_path, "session_s1.pcm", 64000)
    store = SessionStore()

    session = store.create_session(1, "s1", 7, "t", audio_dir=str(tmp_path))

    assert session["audio_file_size"] == 64000
    assert os.path.getsize(path) == 64000


def test_in_memory_store_still_creates_a_fresh_file(tmp_path):
    session = SessionStore().create_session(1, "s2", 7, "t", audio_dir=str(tmp_path))
    assert session["audio_file_size"] == 0
    assert os.path.getsize(session["audio_file_path"]) == 0


@pytest.fixture
def redis_store(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(session_store_redis.redis, "from_url", lambda *a, **k: client)
    return session_store_redis.RedisSessionStore("redis://unused"), client


def test_redis_store_adopts_existing_audio(tmp_path, redis_store):
    store, client = redis_store
    path = _make(tmp_path, "session_s3.pcm", 64000)

    session = store.create_session(1, "s3", 7, "t", audio_dir=str(tmp_path))

    assert session["audio_file_size"] == 64000
    assert os.path.getsize(path) == 64000
    stored = client.pipeline.return_value.hset.call_args.kwargs["mapping"]
    assert stored["audio_file_size"] == "64000"
