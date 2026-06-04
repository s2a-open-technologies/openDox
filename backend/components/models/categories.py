from typing import Optional
from sqlmodel import Field, SQLModel

class CategoriesBase(SQLModel):
    name: str = Field(index=True)
    description: str
    system_prompt: str

class Categories(CategoriesBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class CategoriesCreate(CategoriesBase):
    pass 

class CategoriesRead(CategoriesBase):
    id: int