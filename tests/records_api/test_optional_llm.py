"""The LLM step is optional: globally (LlmSettingsModel) and per category.

Without it the pipeline only transcribes, ``Record.summarize`` stays empty in
the DB and the API serves the transcript as ``summarize`` — the desktop client
reads nothing else and must keep working unchanged.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

import backend.components.services.background_transcription_service as bts
import backend.components.services.llm_gate as llm_gate
from backend.components.models.categories import Categories
from backend.components.models.llm_settings_model import LlmSettingsModel
from backend.components.models.record_model import Record
from backend.components.models.task_model import Task


def _set_global(session_factory, enabled: bool) -> None:
    with session_factory() as session:
        session.add(LlmSettingsModel(llm_enabled=enabled))
        session.commit()


def _category(session_factory, *, llm_enabled: bool) -> int:
    with session_factory() as session:
        cat = Categories(
            name="Diktat",
            description="",
            system_prompt="Strukturiere.",
            llm_enabled=llm_enabled,
        )
        session.add(cat)
        session.commit()
        session.refresh(cat)
        return cat.id


def _record(session_factory, user_id, category_id=None, *, summarize="") -> Record:
    with session_factory() as session:
        task = Task(
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        record = Record(
            session_id=f"session-{task.id}",
            user_id=user_id,
            category_id=category_id,
            title="t",
            content="Patient klagt über Kopfschmerzen.",
            timestamp="01.01.2026 00:00:00",
            summarize=summarize,
            file="",
            task_id=task.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


@pytest.fixture
def llm(monkeypatch):
    """Mocked LLM and sanitizer; fails the test if either is called unexpectedly."""
    model = MagicMock()
    model.generate_response.return_value = "LLM-Zusammenfassung"
    monkeypatch.setattr(llm_gate, "SummarizeModel", lambda *a, **k: model)
    sanitize = MagicMock(return_value=("x", {}))
    monkeypatch.setattr(llm_gate, "sanitize", sanitize)
    return model


@pytest.fixture
def pipeline(monkeypatch, session_factory):
    """Run the background task against the test DB with a fake ASR backend."""
    backend = MagicMock()
    backend.transcribe.return_value = "Patient klagt über Kopfschmerzen."
    monkeypatch.setattr(bts, "session_factory", session_factory)
    monkeypatch.setattr(bts, "get_final_backend", lambda: backend)
    monkeypatch.setattr(bts, "get_whisper_params", lambda: {})
    monkeypatch.setattr(
        bts, "get_settings", lambda: MagicMock(term_correction_enabled=False)
    )

    def run(record: Record) -> None:
        assert bts.background_transcription_task(
            record.task_id, record.session_id, pcm_buffer=b"\0\0\0\0"
        )

    return run


@pytest.mark.parametrize(
    ("global_on", "category_on"), [(False, True), (True, False), (False, False)]
)
def test_pipeline_skips_llm_when_disabled(
    session_factory, create_user, pipeline, llm, global_on, category_on
):
    _set_global(session_factory, global_on)
    record = _record(
        session_factory,
        create_user("dr.a").id,
        _category(session_factory, llm_enabled=category_on),
    )

    pipeline(record)

    llm.generate_response.assert_not_called()
    llm_gate.sanitize.assert_not_called()
    with session_factory() as session:
        stored = session.get(Record, record.id)
        assert stored.summarize == ""
        assert session.get(Task, record.task_id).status == "finished"


def test_pipeline_summarizes_when_enabled(session_factory, create_user, pipeline, llm):
    _set_global(session_factory, True)
    record = _record(
        session_factory,
        create_user("dr.a").id,
        _category(session_factory, llm_enabled=True),
    )

    pipeline(record)

    llm.generate_response.assert_called_once()
    with session_factory() as session:
        assert session.get(Record, record.id).summarize == "LLM-Zusammenfassung"


def test_read_serves_transcript_as_summary(
    client, session_factory, create_user, auth_headers
):
    user = create_user("dr.a")
    record = _record(
        session_factory, user.id, _category(session_factory, llm_enabled=False)
    )

    body = client.get(
        f"/api/v1/records/by-session/{record.session_id}", headers=auth_headers(user)
    ).json()

    assert body["summary_enabled"] is False
    assert body["summarize"] == "Patient klagt über Kopfschmerzen."

    # A transcript edit reaches the summary the client reads.
    client.put(
        f"/api/v1/records/record/{record.id}",
        json={"content": "Neu.", "summarize": "Patient klagt über Kopfschmerzen."},
        headers=auth_headers(user),
    )
    listed = client.get(
        f"/api/v1/records/list-records/{user.id}", headers=auth_headers(user)
    ).json()
    assert listed[0]["summarize"] == "Neu."
    with session_factory() as session:
        assert session.get(Record, record.id).summarize == ""


def test_read_keeps_empty_summary_when_llm_enabled(
    client, session_factory, create_user, auth_headers
):
    user = create_user("dr.a")
    record = _record(
        session_factory, user.id, _category(session_factory, llm_enabled=True)
    )

    body = client.get(
        f"/api/v1/records/record/{record.id}", headers=auth_headers(user)
    ).json()

    assert body["summary_enabled"] is True
    assert body["summarize"] == ""


def test_put_stores_a_real_summary_without_llm(
    client, session_factory, create_user, auth_headers
):
    user = create_user("dr.a")
    record = _record(
        session_factory, user.id, _category(session_factory, llm_enabled=False)
    )

    client.put(
        f"/api/v1/records/record/{record.id}",
        json={"summarize": "Eigene Notiz"},
        headers=auth_headers(user),
    )

    with session_factory() as session:
        assert session.get(Record, record.id).summarize == "Eigene Notiz"


def test_summarize_without_category_llm_returns_transcript(
    client, session_factory, create_user, auth_headers, llm
):
    """The desktop client calls /summarize after switching to such a category."""
    user = create_user("dr.a")
    record = _record(
        session_factory,
        user.id,
        _category(session_factory, llm_enabled=False),
        summarize="Alte Zusammenfassung",
    )

    response = client.post(
        f"/api/v1/records/record/{record.id}/summarize", headers=auth_headers(user)
    )

    assert response.status_code == 200, response.text
    assert response.json()["summarize"] == "Patient klagt über Kopfschmerzen."
    llm.generate_response.assert_not_called()
    with session_factory() as session:
        assert session.get(Record, record.id).summarize == ""


def test_summarize_with_global_llm_off_returns_transcript(
    client, session_factory, create_user, auth_headers, llm
):
    _set_global(session_factory, False)
    user = create_user("dr.a")
    record = _record(
        session_factory, user.id, _category(session_factory, llm_enabled=True)
    )

    body = client.post(
        f"/api/v1/records/record/{record.id}/summarize", headers=auth_headers(user)
    ).json()

    assert body["summarize"] == "Patient klagt über Kopfschmerzen."
    assert body["summary_enabled"] is False
    llm.generate_response.assert_not_called()
