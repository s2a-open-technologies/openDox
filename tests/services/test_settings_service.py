"""Tests for the SettingsService singleton in settings_service.py."""

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import backend.components.models  # noqa: F401  (registers all tables on metadata)
from backend.components.services import settings_service
from backend.components.sql import sql_engine


@pytest.fixture
def patched_engine(monkeypatch):
    """Point sql_engine.engine at an isolated in-memory SQLite DB."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(sql_engine, "engine", engine)

    def query_row(model):
        with Session(engine) as session:
            from sqlmodel import select

            return session.exec(select(model)).first()

    return query_row


def test_get_settings_creates_default_row_when_none_exists(patched_engine):
    from backend.components.models.settings_model import WhisperSettingsModel

    service = settings_service.SettingsService()
    result = service.get_settings()

    assert result is not None
    assert patched_engine(WhisperSettingsModel) is not None


def test_get_settings_only_loads_once_without_invalidation(patched_engine, monkeypatch):
    service = settings_service.SettingsService()

    calls = []
    original = service._load_whisper_settings

    def counting_load():
        calls.append(1)
        original()

    monkeypatch.setattr(service, "_load_whisper_settings", counting_load)

    service.get_settings()
    service.get_settings()

    assert len(calls) == 1


def test_invalidate_cache_forces_reload(patched_engine, monkeypatch):
    service = settings_service.SettingsService()
    service.get_settings()

    calls = []
    original = service._load_whisper_settings

    def counting_load():
        calls.append(1)
        original()

    monkeypatch.setattr(service, "_load_whisper_settings", counting_load)
    service.invalidate_cache()
    service.get_settings()

    assert len(calls) == 1


def test_get_settings_service_returns_same_instance(patched_engine):
    first = settings_service.get_settings_service()
    second = settings_service.get_settings_service()

    assert first is second


def test_whisper_settings_fall_back_to_env_vars(patched_engine, monkeypatch):
    monkeypatch.setenv("WHISPER_API_ENDPOINT", "http://env-whisper:9000")
    monkeypatch.setenv("WHISPER_API_KEY", "env-key")

    service = settings_service.SettingsService()
    result = service.get_settings()

    assert result.live_api_endpoint == "http://env-whisper:9000"
    assert result.live_api_key == "env-key"
    assert result.final_api_endpoint == "http://env-whisper:9000"
    assert result.final_api_key == "env-key"


def test_get_llm_settings_creates_default_row_when_none_exists(patched_engine):
    from backend.components.models.llm_settings_model import LlmSettingsModel

    service = settings_service.SettingsService()
    result = service.get_llm_settings()

    assert result is not None
    assert patched_engine(LlmSettingsModel) is not None
