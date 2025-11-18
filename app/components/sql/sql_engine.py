from typing import Annotated
from sqlmodel import Field, Session, SQLModel, create_engine, select
from fastapi import Depends


sql_file_name = 'general_test_db.db'
sqlite_uri = f"sqlite:///{sql_file_name}"

connect_args = {"check_same_thread": False }
engine = create_engine(sqlite_uri, connect_args=connect_args)


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