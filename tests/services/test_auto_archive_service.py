"""Tests for backend.components.services.auto_archive_service."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import backend.components.models  # noqa: F401  (registers all tables on metadata)
from backend.components.models.record_model import Record
from backend.components.services import auto_archive_service as svc
from backend.components.services.auto_archive_service import (
    _parse_record_timestamp,
    auto_archive_old_records,
)

_NOW = datetime(2026, 9, 29, 12, 0, 0)


@pytest.fixture
def patched_service(monkeypatch):
    """In-memory SQLite engine + module patched to read settings through it."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def factory() -> Session:
        return Session(engine)

    monkeypatch.setattr(svc, "session_factory", factory)
    return factory


def _enable(monkeypatch, days=90, enabled=True):
    """Point the module's settings reader at fixed auto-archive settings."""
    monkeypatch.setattr(
        svc,
        "get_audio_settings",
        lambda: SimpleNamespace(auto_archive_enabled=enabled, auto_archive_days=days),
    )


def _create_record(session_factory, timestamp, archived=False, **overrides):
    defaults = dict(
        session_id=f"sess-{timestamp}",
        user_id=1,
        category_id=None,
        title="Test Record",
        content="content",
        timestamp=timestamp,
        summarize="summary",
        file="",
        archived=archived,
        task_id=None,
    )
    defaults.update(overrides)
    with session_factory() as session:
        record = Record(**defaults)
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def test_parse_timestamp_handles_backend_and_de_locale_formats():
    assert _parse_record_timestamp("01.09.2026 14:30:05") == datetime(
        2026, 9, 1, 14, 30, 5
    )
    assert _parse_record_timestamp("1.9.2026, 14:30") == datetime(2026, 9, 1, 14, 30)
    assert _parse_record_timestamp("") is None
    assert _parse_record_timestamp("unsinn") is None


def test_disabled_setting_is_a_noop(monkeypatch, patched_service):
    # Explicitly disabled (don't rely on defaults / any surrounding DB state)
    _enable(monkeypatch, days=90, enabled=False)
    record_old = _create_record(patched_service, "01.04.2026 08:00:00")

    assert auto_archive_old_records(now=_NOW) == 0

    with patched_service() as session:
        assert session.get(Record, record_old.id).archived is False


def test_zero_days_is_a_noop(monkeypatch, patched_service):
    _enable(monkeypatch, days=0)
    record_old = _create_record(patched_service, "01.04.2026 08:00:00")

    assert auto_archive_old_records(now=_NOW) == 0

    with patched_service() as session:
        assert session.get(Record, record_old.id).archived is False


def test_archives_records_older_than_configured_age(monkeypatch, patched_service):
    _enable(monkeypatch, days=30)
    old = _create_record(patched_service, "01.08.2026 08:00:00")  # ~59d old
    borderline = _create_record(patched_service, "15.09.2026 12:00:00")  # 14d old

    assert auto_archive_old_records(now=_NOW) == 1

    with patched_service() as session:
        assert session.get(Record, old.id).archived is True
        assert session.get(Record, borderline.id).archived is False


def test_exactly_on_threshold_is_archived(monkeypatch, patched_service):
    _enable(monkeypatch, days=30)
    # 30 days minus a second -> fractional age >= 30 after the day division
    record = _create_record(patched_service, "30.08.2026 11:59:59")

    assert auto_archive_old_records(now=_NOW) == 1

    with patched_service() as session:
        assert session.get(Record, record.id).archived is True


def test_record_before_threshold_is_left_alone(monkeypatch, patched_service):
    _enable(monkeypatch, days=30)
    record = _create_record(patched_service, "30.08.2026 12:00:01")

    assert auto_archive_old_records(now=_NOW) == 0

    with patched_service() as session:
        assert session.get(Record, record.id).archived is False


def test_already_archived_records_are_left_alone(monkeypatch, patched_service):
    _enable(monkeypatch, days=7)
    _create_record(patched_service, "01.01.2026 08:00:00", archived=True)

    assert auto_archive_old_records(now=_NOW) == 0


def test_unparsable_timestamp_is_skipped_without_failing_the_run(
    monkeypatch, patched_service, caplog
):
    _enable(monkeypatch, days=7)
    broken = _create_record(patched_service, "Irgendwas")
    old = _create_record(patched_service, "01.01.2026 08:00:00")

    with caplog.at_level("WARNING"):
        assert auto_archive_old_records(now=_NOW) == 1
    assert any("Unparsable record timestamp" in m for m in caplog.messages)

    with patched_service() as session:
        assert session.get(Record, broken.id).archived is False
        assert session.get(Record, old.id).archived is True


def test_individual_commit_failure_does_not_abort_the_run(
    monkeypatch, patched_service, caplog
):
    _enable(monkeypatch, days=7)
    first = _create_record(patched_service, "01.01.2026 08:00:00")
    second = _create_record(patched_service, "02.01.2026 08:00:00")

    # First commit call fails (before the real commit runs), second passes
    # through to the wrapped session so the second record actually persists.
    real_commit = MagicMock(side_effect=[RuntimeError("db blew up"), None])

    class BoomSession:
        def __init__(self, wrapped):
            self._wrapped = wrapped

        def get(self, model, id_):
            return self._wrapped.get(model, id_)

        def exec(self, *a, **kw):
            return self._wrapped.exec(*a, **kw)

        def add(self, obj):
            self._wrapped.add(obj)

        def commit(self):
            real_commit()
            self._wrapped.commit()

        def rollback(self):
            self._wrapped.rollback()

        def close(self):
            self._wrapped.close()

    monkeypatch.setattr(svc, "session_factory", lambda: BoomSession(patched_service()))

    with caplog.at_level("WARNING"):
        count = auto_archive_old_records(now=_NOW)

    assert count == 1
    assert real_commit.call_count == 2
    assert any("db blew up" in m for m in caplog.messages)
    with patched_service() as session:
        assert session.get(Record, first.id).archived is False
        assert session.get(Record, second.id).archived is True


def test_enabled_with_no_matching_records_is_a_zero_noop(monkeypatch, patched_service):
    _enable(monkeypatch, days=3650)
    _create_record(patched_service, "01.09.2026 08:00:00")

    assert auto_archive_old_records(now=_NOW) == 0
