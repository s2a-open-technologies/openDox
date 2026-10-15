"""WebSocket /ws/record: a resumed recording must find its audio on this instance.

The live PCM stays local to the instance that wrote it. If a reconnect reaches an
instance without that file, appending would silently start a new, empty file and
the earlier audio would be missing from the final transcript. The handler must
refuse instead, and leave the session and any file untouched.
"""

import os

import pytest

from backend.components.models.record_model import Record
from backend.components.security.hashing import create_access_token
from backend.components.services.session_store import session_store
from backend.views.record_api import record as record_module


@pytest.fixture
def ws_env(tmp_path, monkeypatch, session_factory, create_user):
    monkeypatch.setattr(record_module, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(
        record_module, "background_transcription_task", lambda *a, **k: None
    )
    monkeypatch.setattr(record_module, "_pcm_file_to_wav_file", lambda pcm, wav: None)

    user = create_user("ws-resume-user")
    session_id = "sess-resume"
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
    created = session_store.create_session(
        user_id=user.id,
        session_id=session_id,
        record_id=record_id,
        title="ws",
        audio_dir=str(tmp_path),
    )
    token = create_access_token(sub=str(user.id))
    yield user, session_id, token, created["audio_file_path"]
    session_store.delete_session(user.id)


def _url(user, session_id, token):
    return (
        f"/api/v1/records/ws/record?session_id={session_id}"
        f"&user_id={user.id}&token={token}&live=0"
    )


def _mark_as_resumed(user, recorded_size):
    """What a dropped recording leaves behind in the store."""
    session_store.update_session(user.id, {"audio_file_size": recorded_size})


def test_missing_audio_file_is_refused_with_a_clear_error(client, ws_env):
    user, session_id, token, pcm_path = ws_env
    os.remove(pcm_path)  # the file lives on another instance
    _mark_as_resumed(user, 64000)

    with client.websocket_connect(_url(user, session_id, token)) as ws:
        message = ws.receive_json()

    assert message["code"] == "recording_audio_unavailable"
    assert "error" in message
    # Nothing was created and the session is untouched, so the right instance
    # can still resume it.
    assert not os.path.exists(pcm_path)
    assert session_store.get_by_session(session_id)["audio_file_size"] == 64000


def test_truncated_audio_file_is_refused(client, ws_env):
    user, session_id, token, pcm_path = ws_env
    with open(pcm_path, "wb") as f:
        f.write(b"\x00" * 1000)
    _mark_as_resumed(user, 64000)

    with client.websocket_connect(_url(user, session_id, token)) as ws:
        message = ws.receive_json()

    assert message["code"] == "recording_audio_unavailable"
    assert os.path.getsize(pcm_path) == 1000  # not appended to
    assert session_store.get_by_session(session_id)["audio_file_size"] == 64000


def test_complete_audio_file_resumes_normally(client, ws_env):
    user, session_id, token, pcm_path = ws_env
    with open(pcm_path, "wb") as f:
        f.write(b"\x00" * 64000)
    _mark_as_resumed(user, 64000)

    with client.websocket_connect(_url(user, session_id, token)) as ws:
        ws.send_bytes(b"\x01" * 4096)
        ws.send_text('{"event": "stop"}')
        message = ws.receive_json()

    assert message["status"] == "finished"


def test_first_connection_without_recorded_audio_is_not_blocked(client, ws_env):
    """Nothing recorded yet means nothing can be lost: a missing file is fine."""
    user, session_id, token, pcm_path = ws_env
    os.remove(pcm_path)  # session created elsewhere, no audio written yet

    with client.websocket_connect(_url(user, session_id, token)) as ws:
        ws.send_bytes(b"\x01" * 4096)
        ws.send_text('{"event": "stop"}')
        message = ws.receive_json()

    assert message["status"] == "finished"
