"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-FileCopyrightText: 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
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

# Standard library
import time
from typing import Optional

# Third party
from sqlmodel import select

# Custom imports
from backend.components.models.audio_settings_model import AudioSettingsModel
from backend.components.models.llm_settings_model import LlmSettingsModel
from backend.components.models.settings_model import WhisperSettingsModel
from backend.components.modules.env import env_or_file
from backend.components.modules.logger import get_logger
from backend.components.sql.sql_engine import get_session_factory

logger = get_logger(__name__)


DEFAULT_CACHE_TTL_S = 30


def _cache_ttl_s() -> float:
    """Seconds a loaded settings row stays cached (``SETTINGS_CACHE_TTL_S``).

    A short TTL is what lets several app instances see an admin's change
    without a restart: ``invalidate_cache()`` only reaches the instance that
    handled the request. ``0`` disables expiry (cache until invalidated).
    """
    raw = env_or_file("SETTINGS_CACHE_TTL_S", str(DEFAULT_CACHE_TTL_S))
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return float(DEFAULT_CACHE_TTL_S)


class SettingsService:
    """Service for managing Whisper, ASR, and LLM settings.

    Provides cached access to settings with automatic fallback to defaults.
    Cached rows expire after ``SETTINGS_CACHE_TTL_S`` (default 30 s).
    """

    _instance: Optional["SettingsService"] = None
    _whisper_settings: Optional[WhisperSettingsModel] = None
    _llm_settings: Optional[LlmSettingsModel] = None
    _audio_settings: Optional[AudioSettingsModel] = None

    def __new__(cls):
        """Return the singleton instance, creating it on first call."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_session_factory"):
            self._session_factory = get_session_factory()
        if not hasattr(self, "_loaded_at"):
            self._loaded_at: dict[str, float] = {}

    def _stale(self, name: str) -> bool:
        """True if cache ``name`` was never loaded or its TTL has run out."""
        loaded = self._loaded_at.get(name)
        if loaded is None:
            return True
        ttl = _cache_ttl_s()
        return ttl > 0 and time.monotonic() - loaded >= ttl

    def get_settings(self) -> WhisperSettingsModel:
        """Get current Whisper settings from database or create defaults."""
        if self._whisper_settings is None or self._stale("whisper"):
            self._load_whisper_settings()
        return self._whisper_settings

    def get_llm_settings(self) -> LlmSettingsModel:
        """Get current LLM settings from database or create defaults."""
        if self._llm_settings is None or self._stale("llm"):
            self._load_llm_settings()
        return self._llm_settings

    def get_audio_settings(self) -> AudioSettingsModel:
        """Get current audio download settings from database or create defaults."""
        if self._audio_settings is None or self._stale("audio"):
            self._load_audio_settings()
        return self._audio_settings

    def _load_whisper_settings(self) -> None:
        """Load Whisper settings from database or create defaults.

        Falls back to environment variables (WHISPER_API_ENDPOINT, WHISPER_API_KEY)
        when the database values are None.
        """
        session = self._session_factory()
        try:
            settings = session.exec(select(WhisperSettingsModel)).first()
            if settings is None:
                logger.info("No Whisper settings found, creating defaults")
                settings = WhisperSettingsModel()
                session.add(settings)
                session.commit()
                session.refresh(settings)

            if not settings.live_api_endpoint:
                env_ep = env_or_file("WHISPER_API_ENDPOINT")
                if env_ep:
                    logger.info(
                        f"Using WHISPER_API_ENDPOINT from env for live: {env_ep}"
                    )
                    settings.live_api_endpoint = env_ep

            if not settings.live_api_key:
                env_key = env_or_file("WHISPER_API_KEY")
                if env_key:
                    settings.live_api_key = env_key

            if not settings.final_api_endpoint:
                env_ep = env_or_file("WHISPER_API_ENDPOINT")
                if env_ep:
                    logger.info(
                        f"Using WHISPER_API_ENDPOINT from env for final: {env_ep}"
                    )
                    settings.final_api_endpoint = env_ep

            if not settings.final_api_key:
                env_key = env_or_file("WHISPER_API_KEY")
                if env_key:
                    settings.final_api_key = env_key

            self._whisper_settings = settings
            self._loaded_at["whisper"] = time.monotonic()
            logger.info("Whisper settings loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper settings: {e}, using defaults")
            self._whisper_settings = WhisperSettingsModel()
            self._loaded_at["whisper"] = time.monotonic()
        finally:
            session.close()

    def _load_llm_settings(self) -> None:
        """Load LLM settings from database or create defaults."""
        session = self._session_factory()
        try:
            settings = session.exec(select(LlmSettingsModel)).first()
            if settings is None:
                logger.info("No LLM settings found, creating defaults")
                settings = LlmSettingsModel()
                session.add(settings)
                session.commit()
                session.refresh(settings)
            self._llm_settings = settings
            self._loaded_at["llm"] = time.monotonic()
            logger.info("LLM settings loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load LLM settings: {e}, using defaults")
            self._llm_settings = LlmSettingsModel()
            self._loaded_at["llm"] = time.monotonic()
        finally:
            session.close()

    def _load_audio_settings(self) -> None:
        """Load audio download settings from database or create defaults."""
        session = self._session_factory()
        try:
            settings = session.exec(select(AudioSettingsModel)).first()
            if settings is None:
                logger.info("No audio settings found, creating defaults")
                settings = AudioSettingsModel()
                session.add(settings)
                session.commit()
                session.refresh(settings)
            self._audio_settings = settings
            self._loaded_at["audio"] = time.monotonic()
            logger.info("Audio settings loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load audio settings: {e}, using defaults")
            self._audio_settings = AudioSettingsModel()
            self._loaded_at["audio"] = time.monotonic()
        finally:
            session.close()

    def invalidate_cache(self) -> None:
        """Invalidate all settings caches. Call this after updating settings."""
        self._whisper_settings = None
        self._llm_settings = None
        self._audio_settings = None
        self._loaded_at = {}
        logger.debug("Settings cache invalidated")

    def reload(self) -> WhisperSettingsModel:
        """Force reload settings from database."""
        self.invalidate_cache()
        return self.get_settings()


# Global singleton instance
_settings_service: Optional[SettingsService] = None


def get_settings_service() -> SettingsService:
    """Get the global settings service instance."""
    global _settings_service
    if _settings_service is None:
        _settings_service = SettingsService()
    return _settings_service


def get_settings() -> WhisperSettingsModel:
    """Convenience function to get current Whisper settings."""
    return get_settings_service().get_settings()


def get_whisper_params() -> dict:
    """Build the anti-hallucination parameter dict for the final transcription."""
    s = get_settings()
    return {
        "temperature": s.temperature,
        "vad_filter": s.vad_filter,
        "vad_min_silence_ms": s.vad_min_silence_ms,
        "condition_on_previous_text": s.condition_on_previous_text,
        "no_speech_threshold": s.no_speech_threshold,
        "compression_ratio_threshold": s.compression_ratio_threshold,
        "log_prob_threshold": s.log_prob_threshold,
        "hallucination_silence_threshold": s.hallucination_silence_threshold,
        "beam_size": s.final_beam_size,
    }


def get_llm_settings() -> LlmSettingsModel:
    """Convenience function to get current LLM settings."""
    return get_settings_service().get_llm_settings()


def get_audio_settings() -> AudioSettingsModel:
    """Convenience function to get current audio download settings."""
    return get_settings_service().get_audio_settings()


def reload_settings() -> WhisperSettingsModel:
    """Force reload settings from database."""
    return get_settings_service().reload()
