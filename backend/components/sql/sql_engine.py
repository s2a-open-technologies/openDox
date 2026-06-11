"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, SQLModel, create_engine

# Import the centralized database URI
from backend.components.sql.db_config import SQLALCHEMY_URI

if SQLALCHEMY_URI.startswith("postgresql"):
    engine = create_engine(SQLALCHEMY_URI, echo=True)
else:
    engine = create_engine(
        SQLALCHEMY_URI, echo=True, connect_args={"check_same_thread": False}
    )


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
