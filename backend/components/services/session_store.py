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

"""In-memory session store for active recordings.

TODO: Replace with Redis for production/multi-instance deployments.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Any


class SessionStore:
    """Manages active recording sessions in memory."""
    
    def __init__(self):
        # user_id -> session_data mapping
        self._sessions: Dict[int, Dict[str, Any]] = {}
        # session_id -> user_id reverse mapping for cleanup
        self._session_to_user: Dict[str, int] = {}
    
    def create_session(
        self, 
        user_id: int, 
        session_id: str, 
        record_id: int,
        title: str,
        category_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a new recording session for a user.
        
        Replaces any existing session for this user.
        """
        # Remove old session if exists
        self._remove_user_session(user_id)
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "record_id": record_id,
            "title": title,
            "category_id": category_id,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "status": "recording",  # recording, paused
            # Live transcription state - kept here so a resumed recording
            # gets its live stream back (will live in Redis later).
            "audio_buffer": bytearray(),
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
            # Update last activity
            session["last_activity"] = datetime.now()
        return session
    
    def update_session(self, user_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
        """Internal: Remove session and clean up reverse mapping."""
        session = self._sessions.pop(user_id, None)
        if session:
            self._session_to_user.pop(session.get("session_id"), None)
            return True
        return False
    
    def get_user_by_session(self, session_id: str) -> Optional[int]:
        """Get user_id for a given session_id."""
        return self._session_to_user.get(session_id)

    def get_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data by session_id (convenience reverse lookup)."""
        user_id = self._session_to_user.get(session_id)
        if user_id is None:
            return None
        session = self._sessions.get(user_id)
        if session:
            session["last_activity"] = datetime.now()
        return session

    def append_audio(self, session_id: str, chunk: bytes) -> None:
        """Append raw audio bytes to the session's live buffer."""
        session = self.get_by_session(session_id)
        if session is not None:
            session["audio_buffer"].extend(chunk)

    def set_live_state(
        self, session_id: str, last_index: int, live_text: str
    ) -> None:
        """Update live transcription progress for a session."""
        session = self.get_by_session(session_id)
        if session is not None:
            session["last_index"] = last_index
            session["live_text"] = live_text
    
    def cleanup_stale_sessions(self, max_age_minutes: int = 30) -> int:
        """Remove sessions inactive for longer than max_age_minutes.
        
        Returns number of cleaned up sessions.
        """
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        to_remove = [
            user_id for user_id, session in self._sessions.items()
            if session.get("last_activity", datetime.now()) < cutoff
        ]
        
        for user_id in to_remove:
            self._remove_user_session(user_id)
        
        return len(to_remove)


# Global instance - will be replaced by Redis in production
session_store = SessionStore()
