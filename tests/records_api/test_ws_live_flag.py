"""WebSocket /ws/record: live=0 records audio only, without any live ASR."""

import pytest

from backend.components.models.record_model import Record
from backend.components.security.hashing import create_access_token
from backend.components.services.session_store import session_store
from backend.views.record_api import record as record_module


@pytest.fixture
def ws_env(tmp_path, monkeypatch, session_factory, create_user):
    """A user with an open record/session; heavy background work is stubbed out."""
    monkeypatch.setattr(record_module, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(
        record_module, "background_transcription_task", lambda *a, **k: None
    )
    monkeypatch.setattr(record_module, "_pcm_file_to_wav_file", lambda pcm, wav: None)

    user = create_user("ws-live-user")
    session_id = "sess-live-flag"
    with session_factory() as session:
        rec = Record(
            session_id=session_id,
            user_id=user.id,
            title="ws",
            content="",
            timestamp="01.01.2026 00:00:00",
            summarize="",
            file="",
        )
        session.add(rec)
        session.commit()
        session.refresh(rec)
        record_id = rec.id
    session_store.create_session(
        user_id=user.id,
        session_id=session_id,
        record_id=record_id,
        title="ws",
        audio_dir=str(tmp_path),
    )
    token = create_access_token(sub=str(user.id))
    yield user, session_id, token
    session_store.delete_session(user.id)


def _url(user, session_id, token, extra=""):
    return (
        f"/api/v1/records/ws/record?session_id={session_id}"
        f"&user_id={user.id}&token={token}{extra}"
    )


def _record_and_stop(client, url):
    messages = []
    with client.websocket_connect(url) as ws:
        ws.send_bytes(b"\x00" * 4096)
        ws.send_text('{"event": "stop"}')
        messages.append(ws.receive_json())
    return messages


def test_live_off_skips_live_asr_and_still_finishes(client, ws_env, monkeypatch):
    user, session_id, token = ws_env

    calls = []

    def _spy():
        # An exception would be swallowed by the handler's try/except, so count calls.
        calls.append(1)
        raise RuntimeError("live ASR must not be touched when live=0")

    monkeypatch.setattr(record_module, "get_live_asr", _spy)

    messages = _record_and_stop(client, _url(user, session_id, token, "&live=0"))

    assert not calls
    assert messages[0]["status"] == "finished"
    assert "task_id" in messages[0]
    assert not any("partial" in m or "text" in m for m in messages)


def test_live_default_still_asks_for_live_asr(client, ws_env, monkeypatch):
    user, session_id, token = ws_env
    calls = []

    class _NoStream:
        def supports_streaming(self):
            return False

    def _fake_live_asr():
        calls.append(1)
        return _NoStream()

    monkeypatch.setattr(record_module, "get_live_asr", _fake_live_asr)

    # No live parameter -> unchanged behaviour: the live backend is consulted.
    _record_and_stop(client, _url(user, session_id, token))

    assert calls
