"""Tests for GET /tasks/failed and POST /tasks/{id}/retry.

background_transcription_task and audio_storage are mocked throughout — these
tests only cover the endpoint's own request handling (auth, state
transitions, S3 fetch-back for archived audio), not the transcription
pipeline or a real S3 server.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import backend.views.record_api.record as record_module
from backend.components.models.record_model import Record
from backend.components.models.task_model import Task


def _create_error_task(session_factory, **overrides) -> Task:
    defaults = dict(
        status="error",
        error="boom",
        retry_audio_path=None,
        retry_audio_in_s3=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    with session_factory() as session:
        task = Task(**defaults)
        session.add(task)
        session.commit()
        session.refresh(task)
        return task


def _link_record_to_task(session_factory, user_id: int, task_id: int) -> Record:
    with session_factory() as session:
        record = Record(
            session_id=f"session-task-{task_id}",
            user_id=user_id,
            title="Failed task test",
            content="",
            timestamp="01.01.2026 00:00:00",
            summarize="",
            file="",
            task_id=task_id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def test_list_failed_tasks_requires_admin(client, create_user, auth_headers):
    user = create_user("dr.mueller", role="user")

    response = client.get("/api/v1/records/tasks/failed", headers=auth_headers(user))

    assert response.status_code == 403


def test_list_failed_tasks_reports_archived_flag(
    client, create_user, auth_headers, session_factory
):
    admin = create_user("admin", role="admin")
    task = _create_error_task(
        session_factory,
        retry_audio_path="archive/task_1.wav.enc",
        retry_audio_in_s3=True,
    )
    _link_record_to_task(session_factory, admin.id, task.id)

    response = client.get("/api/v1/records/tasks/failed", headers=auth_headers(admin))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["task_id"] == task.id
    assert body[0]["archived"] is True


def test_retry_local_audio_resets_task_and_fires_pipeline(
    monkeypatch, client, create_user, auth_headers, session_factory, tmp_path
):
    admin = create_user("admin", role="admin")
    audio_file = tmp_path / "task_1.wav"
    audio_file.write_bytes(b"fake-audio")
    task = _create_error_task(session_factory, retry_audio_path=str(audio_file))
    _link_record_to_task(session_factory, admin.id, task.id)

    bg_task = MagicMock(return_value=True)
    monkeypatch.setattr(record_module, "background_transcription_task", bg_task)

    response = client.post(
        f"/api/v1/records/tasks/{task.id}/retry", headers=auth_headers(admin)
    )

    assert response.status_code == 200
    assert response.json() == {"task_id": task.id, "status": "pending"}
    with session_factory() as session:
        refreshed = session.get(Task, task.id)
        assert refreshed.status == "pending"
        assert refreshed.retry_audio_path is None
        assert refreshed.retry_audio_in_s3 is False


def test_retry_missing_local_audio_returns_410(
    client, create_user, auth_headers, session_factory
):
    admin = create_user("admin", role="admin")
    task = _create_error_task(
        session_factory, retry_audio_path="/nonexistent/task_1.wav"
    )
    _link_record_to_task(session_factory, admin.id, task.id)

    response = client.post(
        f"/api/v1/records/tasks/{task.id}/retry", headers=auth_headers(admin)
    )

    assert response.status_code == 410


def test_retry_archived_audio_fetches_from_s3(
    monkeypatch, client, create_user, auth_headers, session_factory, tmp_path
):
    admin = create_user("admin", role="admin")
    task = _create_error_task(
        session_factory,
        retry_audio_path="archive/task_1.wav.enc",
        retry_audio_in_s3=True,
    )
    _link_record_to_task(session_factory, admin.id, task.id)

    monkeypatch.chdir(tmp_path)
    download = MagicMock(return_value=b"encrypted-bytes")
    delete = MagicMock()
    monkeypatch.setattr(record_module.audio_storage, "download_bytes", download)
    monkeypatch.setattr(record_module.audio_storage, "delete", delete)
    monkeypatch.setattr(record_module, "decrypt_bytes", lambda data: b"plaintext-wav")
    bg_task = MagicMock(return_value=True)
    monkeypatch.setattr(record_module, "background_transcription_task", bg_task)

    response = client.post(
        f"/api/v1/records/tasks/{task.id}/retry", headers=auth_headers(admin)
    )

    assert response.status_code == 200
    download.assert_called_once_with("archive/task_1.wav.enc")
    delete.assert_called_once_with("archive/task_1.wav.enc")
    restored = tmp_path / "chunks" / "failed" / f"task_{task.id}.wav"
    assert restored.exists()
    assert restored.read_bytes() == b"plaintext-wav"
    with session_factory() as session:
        refreshed = session.get(Task, task.id)
        assert refreshed.retry_audio_in_s3 is False


def test_retry_archived_audio_missing_in_s3_returns_410(
    monkeypatch, client, create_user, auth_headers, session_factory, tmp_path
):
    admin = create_user("admin", role="admin")
    task = _create_error_task(
        session_factory,
        retry_audio_path="archive/task_1.wav.enc",
        retry_audio_in_s3=True,
    )
    _link_record_to_task(session_factory, admin.id, task.id)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        record_module.audio_storage, "download_bytes", MagicMock(return_value=None)
    )

    response = client.post(
        f"/api/v1/records/tasks/{task.id}/retry", headers=auth_headers(admin)
    )

    assert response.status_code == 410
    with session_factory() as session:
        refreshed = session.get(Task, task.id)
        assert refreshed.status == "error"  # untouched


def test_discard_removes_local_audio_and_leaves_the_retry_list(
    client, create_user, auth_headers, session_factory, tmp_path
):
    from sqlmodel import select

    from backend.components.models.audit_model import AuditEvent

    admin = create_user("admin", role="admin")
    owner = create_user("dr.mueller")
    audio = tmp_path / "task_1.wav"
    audio.write_bytes(b"RIFF")
    task = _create_error_task(session_factory, retry_audio_path=str(audio))
    record = _link_record_to_task(session_factory, owner.id, task.id)
    headers = auth_headers(admin)

    response = client.delete(
        f"/api/v1/records/tasks/{task.id}/retained-audio", headers=headers
    )

    assert response.status_code == 200
    assert not audio.exists()
    assert client.get("/api/v1/records/tasks/failed", headers=headers).json() == []
    with session_factory() as session:
        stored = session.get(Task, task.id)
        assert stored.retry_audio_path is None and stored.status == "error"
        # The recording stays with its owner.
        assert session.get(Record, record.id) is not None
        event = session.exec(
            select(AuditEvent).where(AuditEvent.action == "task.discard")
        ).one()
    assert event.details == {"record_id": record.id}


def test_discard_deletes_archived_audio_from_s3(
    client, create_user, auth_headers, session_factory, monkeypatch
):
    admin = create_user("admin", role="admin")
    task = _create_error_task(
        session_factory,
        retry_audio_path="archive/task_1.wav.enc",
        retry_audio_in_s3=True,
    )
    _link_record_to_task(session_factory, admin.id, task.id)
    delete = MagicMock()
    monkeypatch.setattr(
        "backend.components.services.retained_audio.audio_storage.delete", delete
    )

    response = client.delete(
        f"/api/v1/records/tasks/{task.id}/retained-audio", headers=auth_headers(admin)
    )

    assert response.status_code == 200
    delete.assert_called_once_with("archive/task_1.wav.enc")


def test_discard_requires_admin_and_retained_audio(
    client, create_user, auth_headers, session_factory
):
    admin = create_user("admin", role="admin")
    user = create_user("dr.mueller")
    task = _create_error_task(session_factory)
    url = f"/api/v1/records/tasks/{task.id}/retained-audio"

    assert client.delete(url, headers=auth_headers(user)).status_code == 403
    assert client.delete(url, headers=auth_headers(admin)).status_code == 409
    assert (
        client.delete(
            "/api/v1/records/tasks/999/retained-audio", headers=auth_headers(admin)
        ).status_code
        == 404
    )


def test_deleting_the_record_also_removes_its_retained_audio(
    client, create_user, auth_headers, session_factory, tmp_path
):
    owner = create_user("dr.mueller")
    audio = tmp_path / "task_2.wav"
    audio.write_bytes(b"RIFF")
    task = _create_error_task(session_factory, retry_audio_path=str(audio))
    record = _link_record_to_task(session_factory, owner.id, task.id)

    response = client.delete(
        f"/api/v1/records/record/{record.id}", headers=auth_headers(owner)
    )

    assert response.status_code == 200
    assert not audio.exists()
    with session_factory() as session:
        assert session.get(Task, task.id).retry_audio_path is None
