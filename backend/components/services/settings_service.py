# Standard library
from functools import lru_cache
from typing import Optional

# Third party
from sqlmodel import Session, select

# Custom imports
from backend.components.models.settings_model import WhisperSettingsModel
from backend.components.sql.sql_engine import get_session_factory
from backend.components.modules.logger import get_logger

logger = get_logger(__name__)


class SettingsService:
    """Service for managing Whisper and ASR settings.
    
    Provides cached access to settings with automatic fallback to defaults.
    """
    
    _instance: Optional['SettingsService'] = None
    _settings: Optional[WhisperSettingsModel] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_session_factory'):
            self._session_factory = get_session_factory()
    
    def get_settings(self) -> WhisperSettingsModel:
        """Get current settings from database or create defaults."""
        if self._settings is None:
            self._load_settings()
        return self._settings
    
    def _load_settings(self) -> None:
        """Load settings from database or create defaults."""
        session = self._session_factory()
        try:
            settings = session.exec(select(WhisperSettingsModel)).first()
            if settings is None:
                logger.info("No settings found, creating defaults")
                settings = WhisperSettingsModel()
                session.add(settings)
                session.commit()
                session.refresh(settings)
            self._settings = settings
            logger.info("Settings loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load settings: {e}, using defaults")
            self._settings = WhisperSettingsModel()
        finally:
            session.close()
    
    def invalidate_cache(self) -> None:
        """Invalidate the settings cache. Call this after updating settings."""
        self._settings = None
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
    """Convenience function to get current settings."""
    return get_settings_service().get_settings()


def reload_settings() -> WhisperSettingsModel:
    """Force reload settings from database."""
    return get_settings_service().reload()
