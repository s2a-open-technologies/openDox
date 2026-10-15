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


# --- cache expiry: another app instance may have changed the settings --------


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    fake = _Clock()
    monkeypatch.setattr(settings_service.time, "monotonic", fake)
    monkeypatch.setenv("SETTINGS_CACHE_TTL_S", "30")
    return fake


def _set_language(engine_query, language):
    from sqlmodel import Session, select

    from backend.components.models.settings_model import WhisperSettingsModel
    from backend.components.sql import sql_engine

    with Session(sql_engine.engine) as session:
        row = session.exec(select(WhisperSettingsModel)).first()
        row.language = language
        session.add(row)
        session.commit()


def test_settings_are_cached_within_ttl(patched_engine, clock):
    service = settings_service.SettingsService()
    first = service.get_settings()
    clock.now += 29
    assert service.get_settings() is first


def test_change_made_by_another_instance_is_seen_after_ttl(patched_engine, clock):
    service = settings_service.SettingsService()
    assert service.get_settings().language == "de"

    _set_language(patched_engine, "en")  # what another replica would have saved
    assert service.get_settings().language == "de"  # still cached

    clock.now += 31
    assert service.get_settings().language == "en"


def test_llm_and_audio_settings_expire_too(patched_engine, clock):
    service = settings_service.SettingsService()
    llm, audio = service.get_llm_settings(), service.get_audio_settings()
    clock.now += 31
    assert service.get_llm_settings() is not llm
    assert service.get_audio_settings() is not audio


def test_ttl_zero_keeps_the_cache_until_invalidated(patched_engine, clock, monkeypatch):
    monkeypatch.setenv("SETTINGS_CACHE_TTL_S", "0")
    service = settings_service.SettingsService()
    first = service.get_settings()
    clock.now += 100000
    assert service.get_settings() is first
