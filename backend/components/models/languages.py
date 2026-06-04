from typing import Optional
from sqlmodel import Field, SQLModel

class LanguagesBase(SQLModel):
    name: str = Field(index=True)
    country_code: str
    system_prompt: str

class Languages(LanguagesBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class LanguagesCreate(LanguagesBase):
    pass 

class LanguagesRead(LanguagesBase):
    id: int