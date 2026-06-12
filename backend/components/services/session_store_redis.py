"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

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

"""Redis-backed session store for active recordings.

Drop-in replacement for SessionStore with identical interface.
Stores session metadata in Redis hashes; audio data stays on disk.
Falls back gracefully on connection errors via logging.
"""

import os
from datetime import datetime
from typing import Any, Dict, Optional

import redis

from backend.components.modules.logger import get_logger

logger = get_logger(__name__)

_SESSION_TTL_SECONDS = 1800  # 30 minutes


def _serialize_value(value: Any) -> str:
    """Convert a Python value to a Redis-safe string."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return ""
    return str(value)


def _deserialize_value(key: str, value: Optional[str]) -> Any:
    """Convert a Redis string back to the appropriate Python type."""
    if value is None:
        return None
    if key == "user_id" or key == "record_id":
        return int(value) if value else 0
    if key == "category_id":
        return int(value) if value else None
    if key in ("audio_file_size", "last_index", "last_cleanup_len"):
        return int(value) if value else 0
    if key in ("last_cleanup_time",):
        return float(value) if value else 0.0
    if key in ("created_at", "last_activity"):
        return datetime.fromisoformat(value) if value else datetime.now()
    if key == "audio_file_path":
        return value if value else None
    return value


class RedisSessionStore:
    """Manages active recording sessions in Redis.

    Audio data is stored on disk (PCM files); Redis holds only metadata.
    Provides the same interface as SessionStore for transparent swapping.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._ttl = _SESSION_TTL_SECONDS
        logger.info("RedisSessionStore connected to %s", redis_url)

    def ping(self) -> bool:
        """Check Redis connectivity. Raises on failure."""
        return self._redis.ping()

    def _key(self, user_id: int) -> str:
        return f"session:{user_id}"

    def _map_key(self, session_id: str) -> str:
        return f"session_map:{session_id}"

    def _refresh_ttl(self, user_id: int, session_id: str) -> None:
        """Refresh TTL on both keys."""
        pipe = self._redis.pipeline()
        pipe.expire(self._key(user_id), self._ttl)
        pipe.expire(self._map_key(session_id), self._ttl)
        pipe.execute()

    def _dict_from_hash(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Load a session dict from Redis. Returns None if not found."""
        raw = self._redis.hgetall(self._key(user_id))
        if not raw:
            return None
        session = {}
        for k, v in raw.items():
            session[k] = _deserialize_value(k, v)
        return session

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
        self.delete_session(user_id)

        _audio_dir = audio_dir or "."
        os.makedirs(_audio_dir, exist_ok=True)
        _audio_path = os.path.join(_audio_dir, f"session_{session_id}.pcm")
        open(_audio_path, "wb").close()

        now = datetime.now()
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "record_id": record_id,
            "title": title,
            "category_id": _serialize_value(category_id),
            "created_at": _serialize_value(now),
            "last_activity": _serialize_value(now),
            "status": "recording",
            "audio_file_path": _audio_path,
            "audio_file_size": "0",
            "last_index": "0",
            "live_text": "",
            "last_cleanup_time": "0.0",
            "last_cleanup_len": "0",
        }

        pipe = self._redis.pipeline()
        pipe.hset(self._key(user_id), mapping=session_data)
        pipe.set(self._map_key(session_id), str(user_id))
        pipe.expire(self._key(user_id), self._ttl)
        pipe.expire(self._map_key(session_id), self._ttl)
        pipe.execute()

        result = {k: _deserialize_value(k, v) for k, v in session_data.items()}
        return result

    def get_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get active session for a user."""
        session = self._dict_from_hash(user_id)
        if session:
            self._redis.hset(
                self._key(user_id), "last_activity", _serialize_value(datetime.now())
            )
            session["last_activity"] = datetime.now()
            session_id = session.get("session_id", "")
            if session_id:
                self._redis.expire(self._map_key(session_id), self._ttl)
        return session

    def update_session(
        self, user_id: int, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update session data."""
        if not self._redis.exists(self._key(user_id)):
            return None
        serialized = {k: _serialize_value(v) for k, v in updates.items()}
        serialized["last_activity"] = _serialize_value(datetime.now())
        self._redis.hset(self._key(user_id), mapping=serialized)
        return self.get_session(user_id)

    def pause_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Mark session as paused."""
        return self.update_session(user_id, {"status": "paused"})

    def resume_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Mark session as recording and update activity."""
        return self.update_session(user_id, {"status": "recording"})

    def delete_session(self, user_id: int) -> bool:
        """Delete user's session and its PCM file."""
        session = self._dict_from_hash(user_id)
        if not session:
            return False

        session_id = session.get("session_id", "")
        pcm_path = session.get("audio_file_path")
        if pcm_path:
            try:
                os.remove(pcm_path)
            except OSError:
                pass

        pipe = self._redis.pipeline()
        pipe.delete(self._key(user_id))
        if session_id:
            pipe.delete(self._map_key(session_id))
        pipe.execute()
        return True

    def get_user_by_session(self, session_id: str) -> Optional[int]:
        """Get user_id for a given session_id."""
        raw = self._redis.get(self._map_key(session_id))
        return int(raw) if raw else None

    def get_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data by session_id."""
        user_id = self.get_user_by_session(session_id)
        if user_id is None:
            return None
        return self.get_session(user_id)

    def append_audio(self, session_id: str, chunk: bytes) -> None:
        """Append raw audio bytes to the session's on-disk PCM file."""
        session = self.get_by_session(session_id)
        if session is None or not session.get("audio_file_path"):
            return
        with open(session["audio_file_path"], "ab") as f:
            f.write(chunk)
        self._redis.hincrby(
            self._key(session["user_id"]), "audio_file_size", len(chunk)
        )

    def set_live_state(self, session_id: str, last_index: int, live_text: str) -> None:
        """Update live transcription progress for a session."""
        user_id = self.get_user_by_session(session_id)
        if user_id is None:
            return
        self._redis.hset(
            self._key(user_id),
            mapping={
                "last_index": str(last_index),
                "live_text": live_text,
                "last_activity": _serialize_value(datetime.now()),
            },
        )
        self._redis.expire(self._key(user_id), self._ttl)
        self._redis.expire(self._map_key(session_id), self._ttl)

    def cleanup_stale_sessions(self, max_age_minutes: int = 30) -> int:
        """Remove sessions inactive for longer than max_age_minutes.

        With Redis TTL this is largely automatic, but this method
        scans for any keys that slipped through and force-deletes them.
        """
        count = 0
        cutoff = datetime.now().timestamp() - max_age_minutes * 60
        cursor = 0
        while True:
            cursor, keys = self._redis.scan(cursor, match="session:*", count=100)
            for key in keys:
                last_activity = self._redis.hget(key, "last_activity")
                if last_activity:
                    try:
                        ts = datetime.fromisoformat(last_activity).timestamp()
                        if ts < cutoff:
                            user_id_raw = self._redis.hget(key, "user_id")
                            if user_id_raw:
                                self.delete_session(int(user_id_raw))
                                count += 1
                    except (ValueError, TypeError):
                        pass
            if cursor == 0:
                break
        return count
