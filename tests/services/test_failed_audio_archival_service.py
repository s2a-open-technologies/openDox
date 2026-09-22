"""Tests for backend.components.services.failed_audio_archival_service.

Covers the periodic archival of chunks/failed/ retry audio to S3 once it's
past FAILED_AUDIO_RETENTION_DAYS — mocks audio_storage/ffmpeg so no real S3
server or ffmpeg binary is needed, and uses the in-memory sqlite
``session_factory`` fixture instead of the module's real-engine one.
"""

import os
import subprocess
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.components.models.task_model import Task
from backend.components.services import failed_audio_archival_service as svc


def _create_error_task(session_factory, retry_audio_path, updated_at, **overrides):
    defaults = dict(
        status="error",
        error="boom",
        retry_audio_path=retry_audio_path,
        retry_audio_in_s3=False,
        created_at=updated_at,
        updated_at=updated_at,
    )
    defaults.update(overrides)
    with session_factory() as session:
        task = Task(**defaults)
        session.add(task)
        session.commit()
        session.refresh(task)
        return task


def test_noop_when_s3_not_configured(monkeypatch, session_factory):
    monkeypatch.setattr(svc, "session_factory", session_factory)
    monkeypatch.setattr(svc.audio_storage, "is_configured", lambda: False)

    assert svc.archive_stale_failed_audio(retention_days=3) == 0


def test_skips_task_updated_within_retention_window(
    monkeypatch, session_factory, tmp_path
):
    monkeypatch.setattr(svc, "session_factory", session_factory)
    monkeypatch.setattr(svc.audio_storage, "is_configured", lambda: True)
    upload = MagicMock()
    monkeypatch.setattr(svc.audio_storage, "upload_bytes", upload)

    src = tmp_path / "task_1.wav"
    src.write_bytes(b"fake-audio")
    _create_error_task(
        session_factory, str(src), datetime.utcnow() - timedelta(hours=1)
    )

    assert svc.archive_stale_failed_audio(retention_days=3) == 0
    upload.assert_not_called()
    assert src.exists()


def test_skips_task_whose_local_file_is_already_gone(monkeypatch, session_factory):
    monkeypatch.setattr(svc, "session_factory", session_factory)
    monkeypatch.setattr(svc.audio_storage, "is_configured", lambda: True)
    upload = MagicMock()
    monkeypatch.setattr(svc.audio_storage, "upload_bytes", upload)

    _create_error_task(
        session_factory,
        "/nonexistent/task_1.wav",
        datetime.utcnow() - timedelta(days=4),
    )

    assert svc.archive_stale_failed_audio(retention_days=3) == 0
    upload.assert_not_called()


def test_archives_wav_directly_without_ffmpeg(monkeypatch, session_factory, tmp_path):
    monkeypatch.setattr(svc, "session_factory", session_factory)
    monkeypatch.setattr(svc.audio_storage, "is_configured", lambda: True)
    monkeypatch.setattr(
        svc,
        "get_audio_settings",
        lambda: SimpleNamespace(
            audio_format="wav", audio_bitrate="64k", audio_sample_rate=16000
        ),
    )
    upload = MagicMock()
    monkeypatch.setattr(svc.audio_storage, "upload_bytes", upload)
    run = MagicMock()
    monkeypatch.setattr(subprocess, "run", run)

    src = tmp_path / "task_1.wav"
    src.write_bytes(b"raw-wav-bytes")
    task = _create_error_task(
        session_factory, str(src), datetime.utcnow() - timedelta(days=4)
    )

    count = svc.archive_stale_failed_audio(retention_days=3)

    assert count == 1
    run.assert_not_called()  # already the target format — no transcode
    assert not os.path.exists(src)
    upload.assert_called_once()
    key, encrypted_payload = upload.call_args[0]
    assert key == f"archive/task_{task.id}.wav.enc"
    assert encrypted_payload != b"raw-wav-bytes"  # was encrypted

    with session_factory() as session:
        refreshed = session.get(Task, task.id)
        assert refreshed.retry_audio_in_s3 is True
        assert refreshed.retry_audio_path == key


def test_transcodes_when_target_format_differs(monkeypatch, session_factory, tmp_path):
    monkeypatch.setattr(svc, "session_factory", session_factory)
    monkeypatch.setattr(svc.audio_storage, "is_configured", lambda: True)
    monkeypatch.setattr(
        svc,
        "get_audio_settings",
        lambda: SimpleNamespace(
            audio_format="mp3", audio_bitrate="64k", audio_sample_rate=16000
        ),
    )
    upload = MagicMock()
    monkeypatch.setattr(svc.audio_storage, "upload_bytes", upload)

    def fake_run(cmd, check, capture_output):
        # Last arg is the ffmpeg output path — write fake transcoded bytes.
        with open(cmd[-1], "wb") as f:
            f.write(b"fake-mp3-bytes")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    src = tmp_path / "task_1.wav"
    src.write_bytes(b"raw-wav-bytes")
    task = _create_error_task(
        session_factory, str(src), datetime.utcnow() - timedelta(days=4)
    )

    count = svc.archive_stale_failed_audio(retention_days=3)

    assert count == 1
    assert not os.path.exists(src)
    key, _ = upload.call_args[0]
    assert key == f"archive/task_{task.id}.mp3.enc"


def test_failed_upload_leaves_local_file_and_task_untouched(
    monkeypatch, session_factory, tmp_path
):
    monkeypatch.setattr(svc, "session_factory", session_factory)
    monkeypatch.setattr(svc.audio_storage, "is_configured", lambda: True)
    monkeypatch.setattr(
        svc,
        "get_audio_settings",
        lambda: SimpleNamespace(
            audio_format="wav", audio_bitrate="64k", audio_sample_rate=16000
        ),
    )
    monkeypatch.setattr(
        svc.audio_storage,
        "upload_bytes",
        MagicMock(side_effect=RuntimeError("S3 unreachable")),
    )

    src = tmp_path / "task_1.wav"
    src.write_bytes(b"raw-wav-bytes")
    task = _create_error_task(
        session_factory, str(src), datetime.utcnow() - timedelta(days=4)
    )

    count = svc.archive_stale_failed_audio(retention_days=3)

    assert count == 0
    assert src.exists()
    with session_factory() as session:
        refreshed = session.get(Task, task.id)
        assert refreshed.retry_audio_in_s3 is False
        assert refreshed.retry_audio_path == str(src)
