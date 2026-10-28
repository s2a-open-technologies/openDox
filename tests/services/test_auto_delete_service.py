"""Tests for backend.components.services.auto_delete_service."""

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import backend.components.models  # noqa: F401  (registers all tables on metadata)
from backend.components.models.audit_model import AuditEvent
from backend.components.models.record_model import Record
from backend.components.models.task_model import Task
from backend.components.models.user_model import User
from backend.components.services import auto_delete_service as svc
from backend.components.services.auto_delete_service import (
    auto_delete_old_records,
    effective_retention_days,
)

_NOW = datetime(2026, 10, 28, 12, 0, 0)
_OLD = "01.01.2026 10:00:00"  # 300 days before _NOW
_RECENT = "18.10.2026 10:00:00"  # 10 days before _NOW


@pytest.fixture
def factory(monkeypatch):
    """In-memory SQLite engine, module patched to use it; audio deletes recorded."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def make() -> Session:
        return Session(engine)

    monkeypatch.setattr(svc, "session_factory", make)
    deleted_keys: list[str] = []
    monkeypatch.setattr(svc.audio_storage, "delete", deleted_keys.append)
    make.deleted_keys = deleted_keys
    return make


def _settings(monkeypatch, enabled=True, days=180):
    monkeypatch.setattr(
        svc,
        "get_audio_settings",
        lambda: SimpleNamespace(auto_delete_enabled=enabled, auto_delete_days=days),
    )


def _user(factory, name, days=None) -> int:
    with factory() as session:
        user = User(name=name, hashed_password="", auto_delete_days=days)
        session.add(user)
        session.commit()
        return user.id


def _record(factory, user_id, timestamp, **overrides) -> int:
    with factory() as session:
        record = Record(
            session_id=f"s-{user_id}-{timestamp}",
            user_id=user_id,
            title="Herr Mustermann",
            content="Befund",
            timestamp=timestamp,
            summarize="",
            file=overrides.pop("file", ""),
            **overrides,
        )
        session.add(record)
        session.commit()
        return record.id


def _remaining(factory) -> set[int]:
    with factory() as session:
        return set(session.exec(select(Record.id)).all())


def test_effective_retention_is_the_shorter_period():
    assert effective_retention_days(180, None) == 180
    assert effective_retention_days(None, 30) == 30
    assert effective_retention_days(180, 30) == 30
    assert effective_retention_days(None, None) is None


def test_global_retention_deletes_old_records_including_archived_and_audio(
    factory, monkeypatch
):
    _settings(monkeypatch, days=180)
    uid = _user(factory, "dr.mueller")
    old = _record(factory, uid, _OLD, file="records/1.mp3.enc")
    old_archived = _record(factory, uid, _OLD, archived=True)
    recent = _record(factory, uid, _RECENT)

    assert auto_delete_old_records(now=_NOW) == 2

    assert _remaining(factory) == {recent}
    assert old not in _remaining(factory) and old_archived not in _remaining(factory)
    assert factory.deleted_keys == ["records/1.mp3.enc"]


def test_personal_retention_applies_only_to_its_owner(factory, monkeypatch):
    _settings(monkeypatch, enabled=False)
    strict = _user(factory, "dr.mueller", days=5)
    other = _user(factory, "dr.schmidt")
    strict_record = _record(factory, strict, _RECENT)
    other_record = _record(factory, other, _RECENT)

    assert auto_delete_old_records(now=_NOW) == 1
    assert _remaining(factory) == {other_record}
    assert strict_record not in _remaining(factory)


def test_nothing_is_deleted_without_any_retention(factory, monkeypatch):
    _settings(monkeypatch, enabled=False)
    uid = _user(factory, "dr.mueller")
    _record(factory, uid, _OLD)

    assert auto_delete_old_records(now=_NOW) == 0
    assert len(_remaining(factory)) == 1


def test_running_transcription_is_skipped(factory, monkeypatch):
    _settings(monkeypatch, days=1)
    uid = _user(factory, "dr.mueller")
    with factory() as session:
        task = Task(status="transcribing")
        session.add(task)
        session.commit()
        task_id = task.id
    running = _record(factory, uid, _OLD, task_id=task_id)

    assert auto_delete_old_records(now=_NOW) == 0
    assert _remaining(factory) == {running}


def test_one_audit_entry_per_run_without_record_details(factory, monkeypatch):
    _settings(monkeypatch, days=180)
    uid = _user(factory, "dr.mueller")
    _record(factory, uid, _OLD)
    _record(factory, uid, _OLD)

    auto_delete_old_records(now=_NOW)

    with factory() as session:
        events = session.exec(select(AuditEvent)).all()
    assert [(e.action, e.details, e.actor_user_id) for e in events] == [
        ("records.auto_delete", {"count": 2}, None)
    ]
