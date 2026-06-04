# models/user.py
from typing import Optional
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, default=None)
    name: str = Field(index=True, unique=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)


class UserBase(SQLModel):
    name: str


class UserCreate(UserBase):
    password: str  # Klartext beim Eingang – wird gehasht gespeichert


class UserRead(UserBase):
    id: int
    is_active: bool
    is_superuser: bool


class UserLogin(SQLModel):
    name: str
    password: str


class UserUpdate(SQLModel):
    name: Optional[str] = None
    password: Optional[str] = None
