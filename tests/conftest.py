"""Shared fixtures for backend route/service tests."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import backend.components.models  # noqa: F401  (registers all tables on metadata)
from backend.components.security.hashing import create_access_token, get_password_hash
from backend.components.services import settings_service
from backend.components.sql.sql_engine import get_session
from backend.views.auth_api import auth_bp
from backend.views.auth_api.oidc_routes import oidc_bp
from backend.views.record_api import record_bp
from backend.views.settings_api import settings_bp


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


@pytest.fixture
def app(session_factory):
    """Minimal FastAPI app wiring only the routers under test."""
    test_app = FastAPI()
    test_app.include_router(auth_bp)
    test_app.include_router(oidc_bp)
    test_app.include_router(record_bp)
    test_app.include_router(settings_bp)

    def override_get_session():
        with session_factory() as session:
            yield session

    test_app.dependency_overrides[get_session] = override_get_session
    return test_app


@pytest.fixture
def client(app):
    """TestClient bound to the minimal test app."""
    return TestClient(app)


@pytest.fixture
def create_user(session_factory):
    """Factory fixture: make_user(name, password, role="user") -> User."""
    from backend.components.models.user_model import User

    def make_user(name: str, password: str = "password123", role: str = "user") -> User:
        with session_factory() as session:
            user = User(
                name=name,
                hashed_password=get_password_hash(password),
                role=role,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    return make_user


@pytest.fixture
def auth_headers():
    """Factory fixture: token_for(user) -> Authorization header dict."""

    def token_for(user) -> dict:
        token = create_access_token(sub=str(user.id))
        return {"Authorization": f"Bearer {token}"}

    return token_for


@pytest.fixture(autouse=True)
def _reset_settings_service_singleton():
    """Reset the SettingsService singleton so tests don't leak cached state."""
    settings_service.SettingsService._instance = None
    settings_service._settings_service = None
    yield
    settings_service.SettingsService._instance = None
    settings_service._settings_service = None
