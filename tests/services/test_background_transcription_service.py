"""Tests for backend.components.services.background_transcription_service.

Covers the pure-logic helpers: format-aware ffmpeg args and the
failed/-dir nesting guard used by the WAV-retry failsafe.
"""

import os

from backend.components.models.categories import Categories
from backend.components.models.record_model import Record
from backend.components.models.user_model import User
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


def test_build_correction_glossary_merges_both_sources():
    result = svc._build_correction_glossary("Sertralin, Metformin", "Ibuprofen")
    assert result == "Sertralin, Metformin\nIbuprofen"


def test_build_correction_glossary_category_only():
    assert svc._build_correction_glossary("Sertralin", None) == "Sertralin"


def test_build_correction_glossary_personal_only():
    assert svc._build_correction_glossary(None, "Ibuprofen") == "Ibuprofen"


def test_build_correction_glossary_neither_returns_none():
    assert svc._build_correction_glossary(None, None) is None
    assert svc._build_correction_glossary("", "") is None


def _make_record_owner_and_category(
    session_factory,
    *,
    category_glossary=None,
    category_whisper_prompt=None,
    personal_glossary=None,
):
    """Create owner/category/record rows and return their ids.

    Returning bare ids (not the ORM objects) avoids DetachedInstanceError
    when a later test re-opens a fresh session — the caller re-fetches
    within whichever session it's actually testing against.
    """
    with session_factory() as session:
        owner = User(
            name="alice",
            hashed_password="x",
            personal_glossary=personal_glossary,
        )
        session.add(owner)
        session.commit()
        session.refresh(owner)

        category = Categories(
            name="Kardiologie",
            description="Herz",
            system_prompt="Fasse zusammen",
            whisper_prompt=category_whisper_prompt,
            glossary=category_glossary,
        )
        session.add(category)
        session.commit()
        session.refresh(category)

        record = Record(
            session_id="sess-1",
            user_id=owner.id,
            category_id=category.id,
            title="t",
            content="",
            timestamp="2026-01-01T00:00:00",
            summarize="",
            file="",
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        return record.id, category.id


def test_resolve_correction_glossary_merges_category_and_personal(session_factory):
    record_id, category_id = _make_record_owner_and_category(
        session_factory,
        category_glossary="Sertralin",
        category_whisper_prompt="unrelated Whisper style hint",
        personal_glossary="Ibuprofen",
    )

    with session_factory() as session:
        record = session.get(Record, record_id)
        category = session.get(Categories, category_id)
        result = svc._resolve_correction_glossary(session, record, category)

    assert result == "Sertralin\nIbuprofen"


def test_resolve_correction_glossary_ignores_whisper_prompt():
    """Regression guard: must read category.glossary, never whisper_prompt."""
    category = Categories(
        name="X",
        description="d",
        system_prompt="s",
        whisper_prompt="should never appear in correction glossary",
        glossary=None,
    )

    result = svc._resolve_correction_glossary(db=None, record=None, category=category)

    assert result is None


def test_resolve_correction_glossary_with_no_category_still_applies_personal(
    session_factory,
):
    record_id, _ = _make_record_owner_and_category(
        session_factory, personal_glossary="Metformin"
    )

    with session_factory() as session:
        record = session.get(Record, record_id)
        result = svc._resolve_correction_glossary(session, record, category=None)

    assert result == "Metformin"


def test_resolve_correction_glossary_with_no_record_is_none(session_factory):
    with session_factory() as session:
        result = svc._resolve_correction_glossary(session, record=None, category=None)

    assert result is None


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
