from typing import Optional
from sqlmodel import Field, SQLModel

from typing import Optional
from sqlmodel import Field, SQLModel, Relationship

class TerminologyBase(SQLModel):
    code: str = Field(index=True, unique=True)  # z.B. "S82.9"
    type: str = Field(index=True)               # "ICD", "OPS" oder "USER"
    official_text: str                          # Der Text aus dem Katalog
    custom_alias: Optional[str] = None          # Dein "Textbaustein" (z.B. "Fraktur rechtes Bein")
    is_protected: bool = Field(default=True)    # Flag für das LLM: "Nicht verändern!"
    year: int = Field(default=2026) 

class Terminology(TerminologyBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class TerminologyRead(TerminologyBase):
    id: int

class TerminologyCreate(TerminologyBase):
    pass
    