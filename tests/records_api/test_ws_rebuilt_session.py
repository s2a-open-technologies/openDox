"""WebSocket /ws/record after the session store lost the session (e.g. restart)."""

import os

from backend.components.models.record_model import Record
from backend.components.security.hashing import create_access_token
from backend.components.services.session_store import session_store
from backend.views.record_api import record as record_module


def test_audio_recorded_before_the_store_was_lost_is_kept(
    client, tmp_path, monkeypatch, session_factory, create_user
):
    seen = {}

    def _capture_pcm(pcm_path, wav_path):
        seen["size"] = os.path.getsize(pcm_path)

    monkeypatch.setattr(record_module, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(
        record_module, "background_transcription_task", lambda *a, **k: None
    )
    monkeypatch.setattr(record_module, "_pcm_file_to_wav_file", _capture_pcm)

    user = create_user("ws-rebuilt-user")
    session_id = "sess-rebuilt"
    with session_factory() as session:
        session.add(
            Record(
                session_id=session_id,
                user_id=user.id,
                title="ws",
                content="",
                timestamp="01.01.2026 00:00:00",
                summarize="",
                file="",
            )
        )
        session.commit()

    # Eight minutes of audio are on disk, but the session store knows nothing.
    (tmp_path / f"session_{session_id}.pcm").write_bytes(b"\x00" * 64000)
    assert session_store.get_by_session(session_id) is None

    token = create_access_token(sub=str(user.id))
    url = (
        f"/api/v1/records/ws/record?session_id={session_id}"
        f"&user_id={user.id}&token={token}&live=0"
    )
    with client.websocket_connect(url) as ws:
        ws.send_bytes(b"\x01" * 4096)
        ws.send_text('{"event": "stop"}')
        assert ws.receive_json()["status"] == "finished"

    assert seen["size"] == 64000 + 4096
    session_store.delete_session(user.id)
