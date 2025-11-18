from sqlmodel import Field, SQLModel
from typing import Optional
from pydantic import BaseModel


class Record(SQLModel, table=True):
    id: int = Field(primary_key=True)
    session_id: int = Field(index=True)
    user_id: int
    title: str = Field()
    content: str = Field()
    timestamp: str = Field()
    summarize: str = Field()
    file: str = Field()


class RecordBase(SQLModel):
    title: str


class RecordCreate(RecordBase):
    session_id: int
    user_id: int
    timestamp: Optional[str] = None
    content: str = Field(default="")
    summarize: str = Field(default="")
    file: str = Field(default="")


class RecordUpdate(RecordBase):
    content: Optional[str] = None
    file: str
    summarize: Optional[str] = None


class RecordRead(RecordBase):
    title: str
    content: str
    summarize: Optional[str] = ""
    timestamp: str


class RecordChunk(BaseModel):
    session_id: int
    user_id: int


class FinalizeRecord(BaseModel):
    session_id: str
    user_id: int