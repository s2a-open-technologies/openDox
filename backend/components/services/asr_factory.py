"""
  openDox - Medical transcription platform
  Copyright (C) 2025  crizz <christopher.abanilla@gmx.de>

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

from typing import Optional

from .asr_backends import (
    ASRBackend,
    OpenAICompatibleBackend,
    DisabledBackend,
)
from backend.components.services.settings_service import get_settings
from backend.components.modules.logger import get_logger

logger = get_logger(__name__)


class ASRFactory:
    """Factory for creating ASR backends based on settings.
    
    Supports API-based transcription services (OpenAI-compatible)
    and a disabled state for testing.
    """
    
    def __init__(self):
        self._live_backend: Optional[ASRBackend] = None
        self._final_backend: Optional[ASRBackend] = None
    
    def get_live_backend(self) -> ASRBackend:
        """Get or create the live transcription backend."""
        if self._live_backend is None:
            self._live_backend = self._create_live_backend()
        return self._live_backend
    
    def get_final_backend(self) -> ASRBackend:
        """Get or create the final transcription backend."""
        if self._final_backend is None:
            self._final_backend = self._create_final_backend()
        return self._final_backend
    
    def _create_live_backend(self) -> ASRBackend:
        """Create backend for live transcription based on settings."""
        settings = get_settings()
        
        if settings.live_backend == "disabled":
            logger.info("Live transcription disabled")
            return DisabledBackend()
        
        # Default / "api"
        if not settings.live_api_endpoint:
            logger.error("Live backend set to 'api' but no endpoint configured")
            return DisabledBackend()
        
        logger.info(f"Using API backend for live: {settings.live_api_endpoint}")
        return OpenAICompatibleBackend(
            endpoint=settings.live_api_endpoint,
            api_key=settings.live_api_key,
            model=settings.live_api_model or "whisper-1",
        )
    
    def _create_final_backend(self) -> ASRBackend:
        """Create backend for final transcription based on settings."""
        settings = get_settings()
        
        if not settings.final_api_endpoint:
            logger.error("Final backend set to 'api' but no endpoint configured")
            return DisabledBackend()
        
        logger.info(f"Using API backend for final: {settings.final_api_endpoint}")
        return OpenAICompatibleBackend(
            endpoint=settings.final_api_endpoint,
            api_key=settings.final_api_key,
            model=settings.final_api_model or "whisper-1",
        )
    
    def reset_backends(self) -> None:
        """Reset cached backends. Call after settings change."""
        self._live_backend = None
        self._final_backend = None
        logger.info("ASR backends reset")


# Global singleton instance
_asr_factory: Optional[ASRFactory] = None


def get_asr_factory() -> ASRFactory:
    """Get the global ASR factory instance."""
    global _asr_factory
    if _asr_factory is None:
        _asr_factory = ASRFactory()
    return _asr_factory


def get_live_backend() -> ASRBackend:
    """Convenience function to get live transcription backend."""
    return get_asr_factory().get_live_backend()


def get_final_backend() -> ASRBackend:
    """Convenience function to get final transcription backend."""
    return get_asr_factory().get_final_backend()


def reset_asr_backends() -> None:
    """Reset all ASR backends (call after settings change)."""
    get_asr_factory().reset_backends()