"""Dictation in another language: transcribe as dictated, translate, summarize.

``content`` keeps the original; the translation goes into its own fields and
is what the summary is built from — and what clients get as ``summarize``
when the category runs no LLM. The target is the instance language.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

import backend.components.services.background_transcription_service as bts
import backend.components.services.llm_gate as llm_gate
from backend.components.models.categories import Categories
from backend.components.models.record_model import Record
from backend.components.models.settings_model import WhisperSettingsModel
from backend.components.models.task_model import Task
from backend.components.models.translation_settings_model import (
    TranslationSettingsModel,
)

RUSSIAN = "Пациент принимает 5 мг. Аллергии нет."


def _record(session_factory, user_id, *, source_language=None, category_id=None):
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
            content="",
            timestamp="01.01.2026 00:00:00",
            summarize="",
            file="",
            task_id=task.id,
            source_language=source_language,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def _category(session_factory, *, llm_enabled=True, whisper_prompt="Ramipril"):
    with session_factory() as session:
        category = Categories(
            name="Diktat",
            description="",
            system_prompt="Strukturiere.",
            whisper_prompt=whisper_prompt,
            llm_enabled=llm_enabled,
        )
        session.add(category)
        session.commit()
        return category.id


def _instance_language(session_factory, language: str) -> None:
    with session_factory() as session:
        session.add(WhisperSettingsModel(language=language))
        session.commit()


class FakeTranslator:
    """Stands in for SummarizeModel in the pipeline: summary + translation."""

    def __init__(self, fail=False):
        self.fail = fail
        self.systems: list[str] = []
        self.summarized: list[str] = []

    def complete(self, system: str, message: str) -> str:
        if self.fail:
            raise RuntimeError("LLM down")
        self.systems.append(system)
        lines = [line.split(". ", 1)[1] for line in message.splitlines()]
        mapping = {
            "Пациент принимает 5 мг.": "Der Patient nimmt 50 mg.",
            "Аллергии нет.": "Keine Allergien.",
        }
        return json.dumps([mapping.get(line, line) for line in lines])

    def generate_response(self, message, custom_system_prompt=None):
        self.summarized.append(message)
        return "Zusammenfassung"


@pytest.fixture
def llm(monkeypatch):
    fake = FakeTranslator()
    monkeypatch.setattr(bts, "SummarizeModel", lambda *a, **k: fake)
    monkeypatch.setattr(llm_gate, "SummarizeModel", lambda *a, **k: fake)
    monkeypatch.setattr(llm_gate, "sanitize", MagicMock(return_value=("x", {})))
    return fake


@pytest.fixture
def pipeline(monkeypatch, session_factory):
    backend = MagicMock()
    backend.transcribe.return_value = RUSSIAN
    monkeypatch.setattr(bts, "session_factory", session_factory)
    monkeypatch.setattr(bts, "get_final_backend", lambda: backend)
    monkeypatch.setattr(bts, "get_whisper_params", lambda: {})
    corrections = MagicMock(side_effect=lambda text, *a: (text, []))
    monkeypatch.setattr(bts, "correct_terms", corrections)
    monkeypatch.setattr(
        bts,
        "get_settings",
        lambda: MagicMock(term_correction_enabled=True, term_correction_threshold=85.0),
    )
    monkeypatch.setattr(bts, "glossary_for_category", lambda *a: ["Ramipril"])

    def run(record: Record) -> bool:
        return bts.background_transcription_task(
            record.task_id, record.session_id, pcm_buffer=b"\0\0\0\0"
        )

    run.backend = backend
    run.corrections = corrections
    return run


def test_foreign_dictation_is_transcribed_as_dictated_and_translated(
    session_factory, create_user, pipeline, llm
):
    record = _record(
        session_factory,
        create_user("dr.a").id,
        source_language="ru",
        category_id=_category(session_factory),
    )

    assert pipeline(record)

    kwargs = pipeline.backend.transcribe.call_args.kwargs
    assert kwargs["language"] == "ru"
    assert kwargs["prompt"] is None  # no German vocabulary hints
    with session_factory() as session:
        stored = session.get(Record, record.id)
        assert stored.content == RUSSIAN
        assert stored.translation == "Der Patient nimmt 50 mg. Keine Allergien."
        assert stored.translation_language == "de"
        segments = json.loads(stored.translation_segments)
        assert segments[0]["missing_numbers"] == ["5"]
        assert segments[0]["extra_numbers"] == ["50"]
        assert segments[1]["missing_numbers"] == []
        assert stored.summarize == "Zusammenfassung"
        assert session.get(Task, record.task_id).status == "finished"
    assert llm.summarized == ["Der Patient nimmt 50 mg. Keine Allergien."]
    assert "from Russian into German" in llm.systems[0]
    # Term correction only on the German translation, never on the original.
    corrected = [call.args[0] for call in pipeline.corrections.call_args_list]
    assert RUSSIAN not in corrected
    assert "Keine Allergien." in corrected


def test_target_is_the_instance_language_without_german_term_correction(
    session_factory, create_user, pipeline, llm
):
    _instance_language(session_factory, "en")
    record = _record(session_factory, create_user("dr.a").id, source_language="ru")

    assert pipeline(record)

    assert "from Russian into English" in llm.systems[0]
    pipeline.corrections.assert_not_called()
    with session_factory() as session:
        assert session.get(Record, record.id).translation_language == "en"


def test_instance_language_dictation_runs_as_before(
    session_factory, create_user, pipeline, llm
):
    pipeline.backend.transcribe.return_value = "Patient nimmt Ramipril."
    record = _record(
        session_factory,
        create_user("dr.a").id,
        category_id=_category(session_factory),
    )

    assert pipeline(record)

    kwargs = pipeline.backend.transcribe.call_args.kwargs
    assert kwargs["language"] == "de"
    assert kwargs["prompt"] == "Ramipril"
    assert llm.systems == []  # nothing translated
    assert llm.summarized == ["Patient nimmt Ramipril."]
    with session_factory() as session:
        assert session.get(Record, record.id).translation is None


def test_translation_failure_keeps_the_transcript(
    session_factory, create_user, pipeline, monkeypatch
):
    broken = FakeTranslator(fail=True)
    monkeypatch.setattr(bts, "SummarizeModel", lambda *a, **k: broken)
    monkeypatch.setattr(bts, "_retain_audio_for_retry", MagicMock())
    record = _record(session_factory, create_user("dr.a").id, source_language="ru")

    assert pipeline(record) is False

    with session_factory() as session:
        assert session.get(Record, record.id).content == RUSSIAN
        assert session.get(Task, record.task_id).status == "error"


def test_without_llm_summary_clients_get_the_translation(
    client, session_factory, create_user, auth_headers, pipeline, llm
):
    user = create_user("dr.a")
    record = _record(
        session_factory,
        user.id,
        source_language="ru",
        category_id=_category(session_factory, llm_enabled=False),
    )
    assert pipeline(record)

    body = client.get(
        f"/api/v1/records/record/{record.id}", headers=auth_headers(user)
    ).json()

    assert body["summary_enabled"] is False
    assert body["summarize"] == "Der Patient nimmt 50 mg. Keine Allergien."
    assert body["content"] == RUSSIAN
    assert body["source_language"] == "ru"
    assert len(body["translation_segments"]) == 2


def test_editing_a_translated_sentence_rechecks_numbers(
    client, session_factory, create_user, auth_headers, pipeline, llm
):
    user = create_user("dr.a")
    record = _record(session_factory, user.id, source_language="ru")
    assert pipeline(record)

    response = client.put(
        f"/api/v1/records/record/{record.id}",
        json={"translation_segments": [{"index": 0, "target": "Nimmt 5 mg."}]},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["translation"] == "Nimmt 5 mg. Keine Allergien."
    assert body["translation_segments"][0]["missing_numbers"] == []
    assert body["translation_segments"][0]["source"] == "Пациент принимает 5 мг."
    bad = client.put(
        f"/api/v1/records/record/{record.id}",
        json={"translation_segments": [{"index": 9, "target": "x"}]},
        headers=auth_headers(user),
    )
    assert bad.status_code == 400


def _enable_translation(session_factory, access="all"):
    with session_factory() as session:
        session.add(
            TranslationSettingsModel(enabled=True, access=access, languages="ru,ar")
        )
        session.commit()


def test_create_needs_the_release_for_another_language(
    client, session_factory, create_user, auth_headers
):
    user = create_user("dr.a")
    payload = {"user_id": user.id, "title": "t", "source_language": "ru"}

    refused = client.post(
        "/api/v1/records/create", json=payload, headers=auth_headers(user)
    )
    assert refused.status_code == 403
    assert refused.json()["detail"]["code"] == "translation_not_available"

    _enable_translation(session_factory)
    created = client.post(
        "/api/v1/records/create", json=payload, headers=auth_headers(user)
    )
    assert created.status_code == 200
    assert created.json()["source_language"] == "ru"

    not_offered = client.post(
        "/api/v1/records/create",
        json={**payload, "source_language": "tr"},
        headers=auth_headers(user),
    )
    assert not_offered.status_code == 403


def test_instance_language_needs_no_release(client, create_user, auth_headers):
    user = create_user("dr.a")

    response = client.post(
        "/api/v1/records/create",
        json={"user_id": user.id, "title": "t", "source_language": "DE"},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    assert response.json()["source_language"] is None


def test_sanitizer_masks_names_before_translation(
    session_factory, create_user, pipeline, monkeypatch
):
    """The LLM never sees a real name; the stored pairs carry them again."""
    from backend.components.models.llm_settings_model import LlmSettingsModel

    with session_factory() as session:
        session.add(
            LlmSettingsModel(
                sanitizer_enabled=True, sanitizer_endpoint="http://entityguard/x"
            )
        )
        session.commit()
    original = "Пациентка Иванова принимает 5 мг."
    masked = "Пациентка [PERSON_1] принимает 5 мг."
    pipeline.backend.transcribe.return_value = original
    calls = []

    def fake_sanitize(text, endpoint, api_key):
        calls.append(text)
        return text.replace("Иванова", "[PERSON_1]"), {"[PERSON_1]": "Иванова"}

    monkeypatch.setattr(llm_gate, "sanitize", fake_sanitize)
    seen: list[tuple[str, str]] = []

    class Model:
        def complete(self, system, message):
            seen.append((system, message))
            return json.dumps(["Die Patientin [PERSON_1] nimmt 5 mg."])

        def generate_response(self, message, custom_system_prompt=None):
            seen.append(("summary", message))
            return "Zusammenfassung"

    monkeypatch.setattr(bts, "SummarizeModel", lambda *a, **k: Model())
    monkeypatch.setattr(llm_gate, "SummarizeModel", lambda *a, **k: Model())
    record = _record(session_factory, create_user("dr.a").id, source_language="ru")

    assert pipeline(record)

    assert calls[0] == original
    assert all("Иванова" not in message for _, message in seen)
    assert masked in seen[0][1]
    assert "[PERSON_1]" in seen[0][0]  # placeholders must be kept
    with session_factory() as session:
        stored = session.get(Record, record.id)
        assert stored.content == original
        assert stored.translation == "Die Patientin Иванова nimmt 5 mg."
        segment = json.loads(stored.translation_segments)[0]
        assert segment["source"] == original
        assert segment["target"] == "Die Patientin Иванова nimmt 5 mg."
        assert segment["missing_numbers"] == []
        assert segment["extra_numbers"] == []


def test_sanitizer_failure_never_sends_unmasked_text(
    session_factory, create_user, pipeline, llm, monkeypatch
):
    from backend.components.models.llm_settings_model import LlmSettingsModel

    with session_factory() as session:
        session.add(
            LlmSettingsModel(
                sanitizer_enabled=True, sanitizer_endpoint="http://entityguard/x"
            )
        )
        session.commit()

    def down(text, endpoint, api_key):
        raise RuntimeError("EntityGuard unreachable")

    monkeypatch.setattr(llm_gate, "sanitize", down)
    monkeypatch.setattr(bts, "_retain_audio_for_retry", MagicMock())
    record = _record(session_factory, create_user("dr.a").id, source_language="ru")

    assert pipeline(record) is False

    assert llm.systems == []  # nothing reached the LLM
    with session_factory() as session:
        assert session.get(Record, record.id).content == RUSSIAN
        assert session.get(Task, record.task_id).status == "error"
