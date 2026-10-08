"""Tests for the stale-task auto-recovery in GET /status/{task_id}.

A background task (backend/components/services/background_transcription_service.py)
can in principle die or hang before reaching a terminal status ('finished' or
'error') — e.g. the configured LLM backend being unreachable before the
5-minute LLM_REQUEST_TIMEOUT_SECONDS timeout was added. When that happens,
the frontend polls forever and the "regenerate summary" button stays
disabled forever (TranscriptView.tsx's isProcessing never clears). These
tests cover the auto-recovery: a non-terminal task with an old updated_at
gets flipped to 'error' the next time its status is read.
"""

from datetime import datetime, timedelta, timezone

from backend.components.models.record_model import Record
from backend.components.models.task_model import Task


def _create_task(session_factory, **overrides) -> Task:
    defaults = dict(
        status="processing_llm",
        result=None,
        error=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    with session_factory() as session:
        task = Task(**defaults)
        session.add(task)
        session.commit()
        session.refresh(task)
        return task


def _link_record_to_task(session_factory, user_id: int, task_id: int) -> Record:
    with session_factory() as session:
        record = Record(
            session_id="session-stale-task",
            user_id=user_id,
            title="Stale task test",
            content="content",
            timestamp="01.01.2026 00:00:00",
            summarize="",
            file="",
            task_id=task_id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def test_stale_non_terminal_task_is_marked_as_error(
    client, create_user, auth_headers, session_factory
):
    owner = create_user("dr.mueller")
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=8)
    task = _create_task(session_factory, status="processing_llm", updated_at=stale_time)
    _link_record_to_task(session_factory, owner.id, task.id)

    response = client.get(
        f"/api/v1/records/status/{task.id}", headers=auth_headers(owner)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]

    with session_factory() as session:
        refreshed = session.get(Task, task.id)
        assert refreshed.status == "error"
        assert refreshed.error


def test_recent_non_terminal_task_is_left_untouched(
    client, create_user, auth_headers, session_factory
):
    owner = create_user("dr.mueller")
    recent_time = datetime.now(timezone.utc) - timedelta(seconds=30)
    task = _create_task(
        session_factory, status="processing_llm", updated_at=recent_time
    )
    _link_record_to_task(session_factory, owner.id, task.id)

    response = client.get(
        f"/api/v1/records/status/{task.id}", headers=auth_headers(owner)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "processing_llm"


def test_stale_terminal_task_is_left_untouched(
    client, create_user, auth_headers, session_factory
):
    owner = create_user("dr.mueller")
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=8)
    task = _create_task(session_factory, status="finished", updated_at=stale_time)
    _link_record_to_task(session_factory, owner.id, task.id)

    response = client.get(
        f"/api/v1/records/status/{task.id}", headers=auth_headers(owner)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "finished"
