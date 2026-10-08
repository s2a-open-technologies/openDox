"""Shared fixtures for security tests."""

import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.components.models.encryption_key_state import (
    EncryptionKeyState,  # noqa: F401
)
from backend.components.models.ldap_model import LdapSettingsModel  # noqa: F401
from backend.components.models.oidc_model import OidcSettingsModel  # noqa: F401
from backend.components.models.record_model import Record  # noqa: F401
from backend.components.models.user_model import User  # noqa: F401


@pytest.fixture
def session_factory():
    """In-memory SQLite engine shared across connections, with tables created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def factory() -> Session:
        return Session(engine)

    return factory


def insert_raw_record(
    session_factory,
    record_id: int,
    content: str,
    summarize: str,
    pii_mapping: str | None = None,
) -> None:
    """Insert a Record row with exact ciphertext, bypassing the EncryptedString type."""
    with session_factory() as session:
        session.execute(
            text(
                "INSERT INTO record "
                "(id, session_id, user_id, category_id, title, content, "
                "timestamp, summarize, file, archived, task_id, pii_mapping) "
                "VALUES (:id, :session_id, :user_id, NULL, :title, :content, "
                ":timestamp, :summarize, :file, 0, NULL, :pii_mapping)"
            ),
            {
                "id": record_id,
                "session_id": f"session-{record_id}",
                "user_id": 1,
                "title": "Test Record",
                "content": content,
                "timestamp": "01.01.2026 00:00:00",
                "summarize": summarize,
                "file": "",
                "pii_mapping": pii_mapping,
            },
        )
        session.commit()
