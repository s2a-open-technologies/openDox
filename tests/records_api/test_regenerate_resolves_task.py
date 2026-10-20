"""A successful POST /record/{id}/summarize resolves the record's failed task.

Without it the transcript view kept showing "Fehler" forever once the
pipeline had failed (e.g. the LLM step timing out), whatever the user did.
The LLM and the audio persistence are mocked; only the state handling is
tested here.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import backend.components.services.background_transcription_service as bts
import backend.views.record_api.record as record_module
from backend.components.models.record_model import Record
from backend.components.models.task_model import Task


def _failed_recording(session_factory, user_id, *, retry_audio_path=None, in_s3=False):
    with session_factory() as session:
        task = Task(
            status="error",
            error="Zeitüberschreitung",
            retry_audio_path=retry_audio_path,
            retry_audio_in_s3=in_s3,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        record = Record(
            session_id=f"session-{task.id}",
            user_id=user_id,
            title="t",
            content="Transkript ist da.",
            timestamp="01.01.2026 00:00:00",
            summarize="",
            file="",
            task_id=task.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record.id, task.id


def _mock_llm(monkeypatch, summary="Neue Zusammenfassung"):
    model = MagicMock()
    model.generate_response.return_value = summary
    monkeypatch.setattr(record_module, "SummarizeModel", lambda *a, **k: model)


def test_regenerate_marks_failed_task_finished_and_deletes_retained_audio(
    client, create_user, auth_headers, session_factory, monkeypatch, tmp_path
):
    _mock_llm(monkeypatch)
    monkeypatch.setattr(bts, "_persist_audio", lambda path, record: None)
    retained = tmp_path / "task_1.wav"
    retained.write_bytes(b"RIFF")
    user = create_user("dr.mueller")
    record_id, task_id = _failed_recording(
        session_factory, user.id, retry_audio_path=str(retained)
    )

    response = client.post(
        f"/api/v1/records/record/{record_id}/summarize", headers=auth_headers(user)
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summarize"] == "Neue Zusammenfassung"
    assert body["task_status"] == "finished"
    assert body["has_audio"] is False
    with session_factory() as session:
        task = session.get(Task, task_id)
        assert task.status == "finished"
        assert task.error is None
        assert task.retry_audio_path is None
    assert not retained.exists()


def test_regenerate_keeps_retained_audio_as_download_when_enabled(
    client, create_user, auth_headers, session_factory, monkeypatch, tmp_path
):
    _mock_llm(monkeypatch)
    persisted = []

    def fake_persist(path, record):
        persisted.append(path)
        return f"records/{record.id}.mp3.enc"

    monkeypatch.setattr(bts, "_persist_audio", fake_persist)
    retained = tmp_path / "task_2.wav"
    retained.write_bytes(b"RIFF")
    user = create_user("dr.mueller")
    record_id, _ = _failed_recording(
        session_factory, user.id, retry_audio_path=str(retained)
    )

    body = client.post(
        f"/api/v1/records/record/{record_id}/summarize", headers=auth_headers(user)
    ).json()

    assert persisted == [str(retained)]
    assert body["has_audio"] is True
    with session_factory() as session:
        assert session.get(Record, record_id).file == f"records/{record_id}.mp3.enc"
    assert not retained.exists()


def test_regenerate_deletes_archived_audio_from_s3(
    client, create_user, auth_headers, session_factory, monkeypatch
):
    _mock_llm(monkeypatch)
    monkeypatch.setattr(bts, "_persist_audio", lambda path, record: None)
    storage = MagicMock()
    storage.download_bytes.return_value = bts.encrypt_bytes(b"RIFF")
    monkeypatch.setattr(bts, "audio_storage", storage)
    user = create_user("dr.mueller")
    record_id, task_id = _failed_recording(
        session_factory, user.id, retry_audio_path="archive/task_9.wav.enc", in_s3=True
    )

    response = client.post(
        f"/api/v1/records/record/{record_id}/summarize", headers=auth_headers(user)
    )

    assert response.json()["task_status"] == "finished"
    storage.delete.assert_called_once_with("archive/task_9.wav.enc")


def test_regenerate_leaves_a_finished_task_alone(
    client, create_user, auth_headers, session_factory, monkeypatch
):
    _mock_llm(monkeypatch)
    user = create_user("dr.mueller")
    record_id, task_id = _failed_recording(session_factory, user.id)
    with session_factory() as session:
        task = session.get(Task, task_id)
        task.status = "finished"
        session.add(task)
        session.commit()

    body = client.post(
        f"/api/v1/records/record/{record_id}/summarize", headers=auth_headers(user)
    ).json()

    assert body["task_status"] == "finished"


def test_failed_regeneration_keeps_the_error(
    client, create_user, auth_headers, session_factory, monkeypatch
):
    model = MagicMock()
    model.generate_response.side_effect = RuntimeError("LLM down")
    monkeypatch.setattr(record_module, "SummarizeModel", lambda *a, **k: model)
    user = create_user("dr.mueller")
    record_id, task_id = _failed_recording(session_factory, user.id)

    response = client.post(
        f"/api/v1/records/record/{record_id}/summarize", headers=auth_headers(user)
    )

    assert response.status_code == 500
    with session_factory() as session:
        assert session.get(Task, task_id).status == "error"
