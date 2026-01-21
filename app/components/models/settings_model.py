from typing import Optional
from sqlmodel import Field, SQLModel

class WhisperSettingsModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    model_size: str = Field(default="base")
    device: str = Field(default="cpu")
    compute_type: str = Field(default="int8")
