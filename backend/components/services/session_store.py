"""openDox - Medical transcription platform
Copyright (C) 2025  S2A Open Technologies gGmbH
SPDX-FileCopyrightText: 2025 S2A Open Technologies gGmbH
SPDX-License-Identifier: AGPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

"""In-memory session store for active recordings.

Used as fallback when REDIS_URL is not configured.
For production/multi-instance deployments, set REDIS_URL to use RedisSessionStore.
"""

import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from backend.components.modules.env import env_or_file
from backend.components.modules.logger import get_logger
from backend.components.services.pcm_file import open_session_audio

logger = get_logger(__name__)


class SessionStore:
    """Manages active recording sessions in memory."""

    def __init__(self):
        self._sessions: Dict[int, Dict[str, Any]] = {}
        self._session_to_user: Dict[str, int] = {}

    def create_session(
        self,
        user_id: int,
        session_id: str,
        record_id: int,
        title: str,
        category_id: Optional[int] = None,
        audio_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new recording session for a user.

        Replaces any existing session for this user.
        """
        self._remove_user_session(user_id)

        _audio_dir = audio_dir or "."
        os.makedirs(_audio_dir, exist_ok=True)
        _audio_path = os.path.join(_audio_dir, f"session_{session_id}.pcm")
        audio_size = open_session_audio(_audio_path)

        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "record_id": record_id,
            "title": title,
            "category_id": category_id,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "status": "recording",
            "audio_file_path": _audio_path,
            "audio_file_size": audio_size,
            "last_index": 0,
            "live_text": "",
        }

        self._sessions[user_id] = session_data
        self._session_to_user[session_id] = user_id

        return session_data

    def get_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get active session for a user."""
        session = self._sessions.get(user_id)
        if session:
            session["last_activity"] = datetime.now()
        return session

    def update_session(
        self, user_id: int, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update session data."""
        session = self._sessions.get(user_id)
        if session:
            session.update(updates)
            session["last_activity"] = datetime.now()
        return session

    def pause_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Mark session as paused."""
        return self.update_session(user_id, {"status": "paused"})

    def resume_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Mark session as recording and update activity."""
        return self.update_session(user_id, {"status": "recording"})

    def delete_session(self, user_id: int) -> bool:
        """Delete user's session."""
        return self._remove_user_session(user_id)

    def _remove_user_session(self, user_id: int) -> bool:
        """Remove session, clean up reverse mapping, and delete PCM file."""
        session = self._sessions.pop(user_id, None)
        if session:
            self._session_to_user.pop(session.get("session_id"), None)
            pcm_path = session.get("audio_file_path")
            if pcm_path:
                try:
                    os.remove(pcm_path)
                except OSError:
                    pass
            return True
        return False

    def get_user_by_session(self, session_id: str) -> Optional[int]:
        """Get user_id for a given session_id."""
        return self._session_to_user.get(session_id)

    def get_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data by session_id."""
        user_id = self._session_to_user.get(session_id)
        if user_id is None:
            return None
        session = self._sessions.get(user_id)
        if session:
            session["last_activity"] = datetime.now()
        return session

    def append_audio(self, session_id: str, chunk: bytes) -> None:
        """Append raw audio bytes to the session's on-disk PCM file."""
        session = self.get_by_session(session_id)
        if session is not None and session.get("audio_file_path"):
            with open(session["audio_file_path"], "ab") as f:
                f.write(chunk)
            session["audio_file_size"] += len(chunk)

    def set_live_state(self, session_id: str, last_index: int, live_text: str) -> None:
        """Update live transcription progress for a session."""
        session = self.get_by_session(session_id)
        if session is not None:
            session["last_index"] = last_index
            session["live_text"] = live_text

    def active_audio_paths(self) -> set[str]:
        """Absolute PCM paths of all known sessions (live or paused)."""
        return {
            os.path.abspath(s["audio_file_path"])
            for s in self._sessions.values()
            if s.get("audio_file_path")
        }

    def cleanup_stale_sessions(self, max_age_minutes: int = 30) -> int:
        """Remove sessions inactive for longer than max_age_minutes."""
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        to_remove = [
            user_id
            for user_id, session in self._sessions.items()
            if session.get("last_activity", datetime.now()) < cutoff
        ]

        for user_id in to_remove:
            self._remove_user_session(user_id)

        return len(to_remove)


def _create_session_store():
    """Factory: return RedisSessionStore if REDIS_URL is set, else In-Memory."""
    redis_url = env_or_file("REDIS_URL")
    if redis_url:
        try:
            from backend.components.services.session_store_redis import (
                RedisSessionStore,
            )

            store = RedisSessionStore(redis_url)
            store.ping()
            logger.info("Session store: Redis (%s)", redis_url)
            return store
        except Exception as exc:
            logger.warning(
                "Redis unavailable (%s), falling back to in-memory: %s",
                redis_url,
                exc,
            )
    logger.info("Session store: In-Memory (no REDIS_URL configured)")
    return SessionStore()


# Mutable module-level holder: record.py imports ``session_store`` (the object)
# at import time, so swapping the factory result after startup needs a mutable
# container that every consumer re-reads on attribute access.
class _SessionStoreRef:
    """Mutable reference to the active session store.

    Lets the Redis-reconnect path swap the underlying store at runtime while
    import-time consumers (``from ... import session_store``) keep working —
    they read through this proxy on every attribute access.
    """

    def __init__(self, store):
        self._store = store

    def get(self):
        """Return the currently active store instance."""
        return self._store

    def set(self, store):
        """Replace the active store instance (reconnect path only)."""
        self._store = store

    def __getattr__(self, name):
        return getattr(self._store, name)


def reconnect_session_store() -> bool:
    """Try to (re)establish the Redis-backed session store.

    Called by the services-health check when Redis is configured but the
    app is running on the in-memory fallback (typical race: the app process
    restarted while Redis was still down — ``depends_on: service_healthy``
    only orders initial ``compose up`` creation, not single-container
    restarts). If REDIS_URL is configured but the store currently is (or
    was degraded to) in-memory, a fresh ``RedisSessionStore`` is built and
    swapped in atomically.

    Returns:
        True if a Redis-backed store is active afterwards (either it was
        already, or the reconnect succeeded); False if REDIS_URL is unset
        or Redis is still unreachable.
    """
    redis_url = env_or_file("REDIS_URL")
    if not redis_url:
        return False

    from backend.components.services.session_store_redis import RedisSessionStore

    current = session_store.get()
    # Duck-type instead of isinstance: the health-check/tests may inject
    # Redis-compatible stand-ins, and isinstance against a patched factory
    # callable would raise TypeError.
    if hasattr(current, "ping") and not isinstance(current, SessionStore):
        try:
            current.ping()
            return True
        except Exception:
            logger.warning("Redis ping failed on existing store; attempting reconnect")

    try:
        store = RedisSessionStore(redis_url)
        store.ping()
    except Exception as exc:
        logger.warning("Redis reconnect failed (%s): %s", redis_url, exc)
        return False

    session_store.set(store)
    logger.info("Session store: Redis (re)connected (%s)", redis_url)
    return True


# Exported name consumed via ``from ... import session_store`` everywhere.
# It IS the mutable proxy — attribute lookups forward to whichever store is
# active, so a runtime reconnect swap is visible to import-time consumers.
# (Defined after reconnect_session_store so the function body can reference
# the module-level name via global lookup at call time.)
session_store = _SessionStoreRef(_create_session_store())
