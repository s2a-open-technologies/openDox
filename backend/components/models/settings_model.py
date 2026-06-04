from typing import Optional
from sqlmodel import Field, SQLModel

class WhisperSettingsModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Live (Near-Real-Time) Transcription Settings
    live_backend: str = Field(default="api")  # "api", "disabled"
    live_api_endpoint: Optional[str] = Field(default=None)
    live_api_key: Optional[str] = Field(default=None)
    live_api_model: Optional[str] = Field(default=None)  # e.g. "whisper-1"
    
    # Final Transcription Settings
    final_backend: str = Field(default="api")  # "api"
    final_api_endpoint: Optional[str] = Field(default=None)
    final_api_key: Optional[str] = Field(default=None)
    final_api_model: Optional[str] = Field(default=None)
    
    # Common Settings
    language: str = Field(default="de")
    chunk_length_s: int = Field(default=3)
    overlap_s: int = Field(default=0)