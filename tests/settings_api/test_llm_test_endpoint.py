"""Tests for GET /api/v1/settings/llm-test/.

Regression coverage for a production bug: the endpoint used to only check
/v1/models reachability, reconstructing the URL correctly (stripping and
re-adding "/v1"). The real client used for summaries (SummarizeModel) did no
such normalization, so a bare endpoint like "https://ollama.com" (no /v1)
passed the connection test while every real summary request silently hit
the provider's website (HTML) instead of its API. The endpoint now probes
through SummarizeModel itself so a green result is a true predictor of real
usage.
"""

from backend.components.models.llm_settings_model import LlmSettingsModel
from backend.views.settings_api import settings_routes


def _create_llm_settings(session_factory, **overrides) -> LlmSettingsModel:
    defaults = dict(
        llm_api_endpoint="https://ollama.com",
        llm_api_key="test-key",
        llm_model="some-model",
        llm_temperature=0.2,
        llm_max_tokens=2048,
    )
    defaults.update(overrides)
    with session_factory() as session:
        settings = LlmSettingsModel(**defaults)
        session.add(settings)
        session.commit()
        session.refresh(settings)
        return settings


def test_returns_400_when_no_endpoint_configured(client, create_user, auth_headers):
    admin = create_user("admin1", role="admin")

    response = client.get("/api/v1/settings/llm-test/", headers=auth_headers(admin))

    assert response.status_code == 400


def test_successful_chat_probe_reports_ok_with_reply_and_models(
    client, create_user, auth_headers, session_factory, monkeypatch
):
    admin = create_user("admin1", role="admin")
    _create_llm_settings(session_factory)

    class FakeSummarizeModel:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def generate_response(self, message, custom_system_prompt=None):
            assert message == "hi bist du da?"
            return "Ja, ich bin da!"

    monkeypatch.setattr(settings_routes, "SummarizeModel", FakeSummarizeModel)

    class FakeModelsResponse:
        status_code = 200

        def json(self):
            return {"data": [{"id": "some-model"}]}

    monkeypatch.setattr(
        settings_routes._requests, "get", lambda *a, **kw: FakeModelsResponse()
    )

    response = client.get("/api/v1/settings/llm-test/", headers=auth_headers(admin))

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["reply"] == "Ja, ich bin da!"
    assert body["models"] == ["some-model"]


def test_chat_probe_failure_reports_ok_false_with_error(
    client, create_user, auth_headers, session_factory, monkeypatch
):
    admin = create_user("admin1", role="admin")
    _create_llm_settings(session_factory)

    class FakeSummarizeModel:
        def __init__(self, **kwargs):
            pass

        def generate_response(self, message, custom_system_prompt=None):
            raise RuntimeError("Expecting value: line 1 column 1 (char 0)")

    monkeypatch.setattr(settings_routes, "SummarizeModel", FakeSummarizeModel)

    response = client.get("/api/v1/settings/llm-test/", headers=auth_headers(admin))

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "Expecting value" in body["error"]


def test_bare_domain_endpoint_is_normalized_for_the_models_probe(
    client, create_user, auth_headers, session_factory, monkeypatch
):
    admin = create_user("admin1", role="admin")
    _create_llm_settings(session_factory, llm_api_endpoint="https://ollama.com")

    class FakeSummarizeModel:
        def __init__(self, **kwargs):
            pass

        def generate_response(self, message, custom_system_prompt=None):
            return "ok"

    monkeypatch.setattr(settings_routes, "SummarizeModel", FakeSummarizeModel)

    captured_urls = []

    class FakeModelsResponse:
        status_code = 200

        def json(self):
            return {"data": []}

    def fake_get(url, headers=None, timeout=None):
        captured_urls.append(url)
        return FakeModelsResponse()

    monkeypatch.setattr(settings_routes._requests, "get", fake_get)

    response = client.get("/api/v1/settings/llm-test/", headers=auth_headers(admin))

    assert response.status_code == 200
    assert captured_urls == ["https://ollama.com/v1/models"]
