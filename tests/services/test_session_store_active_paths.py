"""active_audio_paths(): which PCM files belong to live or resumable sessions."""

import os

from backend.components.services.session_store import SessionStore


def test_in_memory_store_lists_paths_of_its_sessions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = SessionStore()
    assert store.active_audio_paths() == set()

    session = store.create_session(1, "s-1", 10, "Titel", None)

    paths = store.active_audio_paths()
    assert os.path.abspath(session["audio_file_path"]) in paths
