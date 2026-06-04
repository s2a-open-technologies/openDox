from abc import ABC, abstractmethod
from typing import Optional, AsyncGenerator
import numpy as np


class ASRBackend(ABC):
    """Abstract base class for ASR (Automatic Speech Recognition) backends.
    
    Supports API-based transcription services.
    """
    
    @abstractmethod
    def transcribe(
        self, 
        audio: bytes | np.ndarray | str, 
        language: str = "de",
        beam_size: int = 5,
        prompt: str | None = None
    ) -> str:
        """Transcribe audio to text.
        
        Args:
            audio: Audio data (PCM bytes, numpy array) or file path
            language: Language code (e.g., 'de', 'en')
            beam_size: Beam size for decoding (lower = faster)
            prompt: Optional text prompt for context continuation (Whisper / API backends)
            
        Returns:
            Transcribed text
        """
        pass
    
    @abstractmethod
    def supports_streaming(self) -> bool:
        """Whether this backend supports real-time streaming.
        
        For truly streaming APIs (like Voxtral or live WebSocket connections),
        this should return True. Most REST APIs return False.
        """
        return False
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if the backend is healthy and available.
        
        Returns:
            True if backend is ready to transcribe
        """
        pass
    
    def get_chunk_config(self) -> dict:
        """Get recommended chunk configuration for this backend.
        
        Returns:
            Dict with 'chunk_length_s' and 'overlap_s' keys
        """
        # Default configuration
        return {
            "chunk_length_s": 5,
            "overlap_s": 0,
        }