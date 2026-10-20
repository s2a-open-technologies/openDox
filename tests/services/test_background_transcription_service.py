"""Tests for backend.components.services.background_transcription_service.

Covers the pure-logic helpers: format-aware ffmpeg args and the
failed/-dir nesting guard used by the WAV-retry failsafe.
"""

import os

from backend.components.services import background_transcription_service as svc


def test_build_ffmpeg_args_mp3():
    args, ext = svc._build_ffmpeg_args("mp3", "192k")
    assert args == ["-c:a", "libmp3lame", "-b:a", "192k"]
    assert ext == "mp3"


def test_build_ffmpeg_args_wav_has_no_bitrate():
    args, ext = svc._build_ffmpeg_args("wav", "192k")
    assert args == ["-c:a", "pcm_s16le"]
    assert ext == "wav"


def test_build_ffmpeg_args_flac_has_no_bitrate():
    args, ext = svc._build_ffmpeg_args("flac", "192k")
    assert args == ["-c:a", "flac", "-compression_level", "8"]
    assert ext == "flac"


def test_build_ffmpeg_args_ogg_uses_opus():
    args, ext = svc._build_ffmpeg_args("ogg", "320k")
    assert args == ["-c:a", "libopus", "-b:a", "320k"]
    assert ext == "ogg"


def test_build_ffmpeg_args_unknown_format_falls_back_to_mp3():
    args, ext = svc._build_ffmpeg_args("", "64k")
    assert ext == "mp3"
    args2, ext2 = svc._build_ffmpeg_args("aac", "64k")
    assert ext2 == "mp3"
    assert args == args2


def test_retain_audio_for_retry_moves_file_to_failed_dir(tmp_path):
    src = tmp_path / "session_abc.wav"
    src.write_bytes(b"fake-audio")

    class FakeTask:
        retry_audio_path = None

    class FakeDb:
        def get(self, model, task_id):
            return FakeTask()

        def add(self, obj):
            pass

        def commit(self):
            pass

    svc._retain_audio_for_retry(FakeDb(), 42, str(src))

    expected = tmp_path / "failed" / "task_42.wav"
    assert expected.exists()
    assert not src.exists()


def test_should_overwrite_content_with_nonempty_result():
    assert svc._should_overwrite_content("Neuer Text", "Alter Text") is True


def test_should_overwrite_content_empty_result_keeps_existing():
    assert svc._should_overwrite_content("", "Alter Text") is False
    assert svc._should_overwrite_content("   ", "Alter Text") is False


def test_should_overwrite_content_empty_result_with_no_prior_content():
    assert svc._should_overwrite_content("", "") is True
    assert svc._should_overwrite_content("", None) is True


def test_retain_audio_for_retry_does_not_nest_failed_dirs(tmp_path):
    failed_dir = tmp_path / "failed"
    failed_dir.mkdir()
    src = failed_dir / "task_42.wav"
    src.write_bytes(b"fake-audio")

    class FakeTask:
        retry_audio_path = None

    class FakeDb:
        def get(self, model, task_id):
            return FakeTask()

        def add(self, obj):
            pass

        def commit(self):
            pass

    svc._retain_audio_for_retry(FakeDb(), 42, str(src))

    assert not os.path.isdir(failed_dir / "failed")
    assert src.exists()


# --- failed audio goes straight to S3 so any app instance can retry it --------


class _FakeTask:
    retry_audio_path = None
    retry_audio_in_s3 = False


class _FakeDb:
    def __init__(self):
        self.task = _FakeTask()
        self.committed = 0

    def get(self, model, task_id):
        return self.task

    def add(self, obj):
        pass

    def commit(self):
        self.committed += 1

    def rollback(self):
        pass


def _s3(monkeypatch, *, configured=True, key="archive/task_42.wav.enc", error=None):
    from backend.components.services import failed_audio_archival_service as arch

    monkeypatch.setattr(arch.audio_storage, "is_configured", lambda: configured)
    calls = []

    def fake_archive(task_id, file_path):
        calls.append((task_id, file_path))
        if error:
            raise error
        return key

    monkeypatch.setattr(arch, "archive_task_audio", fake_archive)
    return calls


def test_failed_audio_is_uploaded_to_s3_and_local_copy_removed(tmp_path, monkeypatch):
    src = tmp_path / "session_abc.wav"
    src.write_bytes(b"fake-audio")
    calls = _s3(monkeypatch)
    db = _FakeDb()

    svc._retain_audio_for_retry(db, 42, str(src))

    assert calls == [(42, str(src))]
    assert db.task.retry_audio_in_s3 is True
    assert db.task.retry_audio_path == "archive/task_42.wav.enc"
    assert not src.exists()
    assert not (tmp_path / "failed").exists()  # nothing left on local disk


def test_local_retention_is_used_when_s3_is_not_configured(tmp_path, monkeypatch):
    src = tmp_path / "session_abc.wav"
    src.write_bytes(b"fake-audio")
    calls = _s3(monkeypatch, configured=False)
    db = _FakeDb()

    svc._retain_audio_for_retry(db, 42, str(src))

    assert calls == []
    assert (tmp_path / "failed" / "task_42.wav").exists()
    assert db.task.retry_audio_in_s3 is False


def test_failed_s3_upload_falls_back_to_local_retention(tmp_path, monkeypatch):
    """A recording is never lost just because the object store is down."""
    src = tmp_path / "session_abc.wav"
    src.write_bytes(b"fake-audio")
    _s3(monkeypatch, error=RuntimeError("s3 down"))
    db = _FakeDb()

    svc._retain_audio_for_retry(db, 42, str(src))

    assert (tmp_path / "failed" / "task_42.wav").exists()
    assert db.task.retry_audio_in_s3 is False
    assert db.task.retry_audio_path.endswith("task_42.wav")
