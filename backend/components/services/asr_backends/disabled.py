import numpy as np

from .base import ASRBackend


class DisabledBackend(ASRBackend):
    """Placeholder backend when transcription is disabled.
    
    Returns empty strings for all transcriptions.
    Useful for disabling live transcription while keeping final transcription active.
    """
    
    def __init__(self):
        pass
    
    def transcribe(
        self,
        audio: bytes | np.ndarray | str,
        language: str = "de",
        beam_size: int = 5,
        prompt: str | None = None,
    ) -> str:
        """Return empty string (transcription disabled)."""
        return ""
    
    def supports_streaming(self) -> bool:
        """Disabled backend does not support streaming."""
        return False
    
    def health_check(self) -> bool:
        """Always healthy (does nothing)."""
        return True
    
    def get_chunk_config(self) -> dict:
        """Return default config (not used when disabled)."""
        return {
            "chunk_length_s": 5,
            "overlap_s": 0,
        }