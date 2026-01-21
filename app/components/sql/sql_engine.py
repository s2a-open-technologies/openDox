import os
from typing import Annotated
from sqlmodel import Field, Session, SQLModel, create_engine, select
from fastapi import Depends

user = os.getenv("SQL_USER")
password = os.getenv("SQL_PASS")
host = os.getenv("SQL_HOST")
port = os.getenv("SQL_PORT")
database = os.getenv("SQL_DB")


sql_uri = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"

engine = create_engine(sql_uri, echo=True)

def create_db_and_tables():
    """Function to create the databases"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Function to yield the sql session"""
    with Session(engine) as session:
        yield session
        
# Session dependency for later use        
SessionDep = Annotated[Session, Depends(get_session)]

# Session factory für background tasks
def get_session_factory():
    def create():
        return Session(engine)
    return create