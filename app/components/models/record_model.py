from sqlmodel import Field, SQLModel
from typing import Optional
from pydantic import BaseModel


class Record(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    user_id: int
    title: str = Field()
    content: str = Field()
    timestamp: str = Field()
    summarize: str = Field()
    file: str = Field()
    
    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "title": self.title,
            "content": self.content,
            "timestamp": self.timestamp,
            "summarize": self.summarize,
            "file": self.file,
        }


class RecordBase(SQLModel):
    title: str


class RecordCreate(SQLModel):
    user_id: int
    title: str


class RecordUpdate(SQLModel):
    title: Optional[str] = None
    content: Optional[str] = None
    file: Optional[str] = None
    summarize: Optional[str] = None


class RecordRead(RecordBase):
    title: str
    content: str
    summarize: Optional[str] = ""
    timestamp: str


class RecordChunk(BaseModel):
    session_id: str
    user_id: int


class FinalizeRecord(BaseModel):
    session_id: str
    user_id: int