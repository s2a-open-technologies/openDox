"""Orphan cleanup must never touch recordings another instance is writing."""

import os
import time

from backend.components.services.chunk_cleanup import cleanup_orphaned_chunk_files

OLD = 3600  # seconds


def _touch(path, age_s=0):
    path.write_bytes(b"x")
    stamp = time.time() - age_s
    os.utime(path, (stamp, stamp))
    return path


def test_removes_old_unreferenced_session_files(tmp_path):
    pcm = _touch(tmp_path / "session_a.pcm", OLD)
    wav = _touch(tmp_path / "session_a.wav", OLD)

    removed = cleanup_orphaned_chunk_files(str(tmp_path), set(), min_age_s=300)

    assert removed == 2
    assert not pcm.exists() and not wav.exists()


def test_keeps_files_that_are_still_being_written(tmp_path):
    """Another instance on the same volume writes its PCM every ~100 ms."""
    fresh = _touch(tmp_path / "session_live.pcm", age_s=2)

    assert cleanup_orphaned_chunk_files(str(tmp_path), set(), min_age_s=300) == 0
    assert fresh.exists()


def test_keeps_files_of_sessions_that_are_still_registered(tmp_path):
    """A paused recording is old but resumable: it is in the session store."""
    paused = _touch(tmp_path / "session_paused.pcm", OLD)

    removed = cleanup_orphaned_chunk_files(
        str(tmp_path), {os.path.abspath(paused)}, min_age_s=300
    )

    assert removed == 0
    assert paused.exists()


def test_ignores_other_files_and_the_failed_directory(tmp_path):
    other = _touch(tmp_path / "notes.txt", OLD)
    failed_dir = tmp_path / "failed"
    failed_dir.mkdir()
    retained = _touch(failed_dir / "task_7.wav", OLD)

    assert cleanup_orphaned_chunk_files(str(tmp_path), set(), min_age_s=300) == 0
    assert other.exists() and retained.exists()


def test_missing_directory_is_fine(tmp_path):
    assert cleanup_orphaned_chunk_files(str(tmp_path / "nope"), set(), 300) == 0
