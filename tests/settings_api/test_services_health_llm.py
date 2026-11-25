"""LLM entry of GET /api/v1/settings/services-health/ (System tab)."""

import pytest
import requests

from backend.components.models.llm_settings_model import LlmSettingsModel
from backend.views.settings_api import settings_routes


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body


def _llm_status(client, admin, auth_headers) -> str:
    response = client.get(
        "/api/v1/settings/services-health/", headers=auth_headers(admin)
    )
    assert response.status_code == 200
    return {s["name"]: s["status"] for s in response.json()["services"]}["LLM"]


def _configure(session_factory, **overrides):
    values = dict(
        llm_api_endpoint="http://llm.test/v1", llm_model="qwen", llm_enabled=True
    )
    values.update(overrides)
    with session_factory() as session:
        session.add(LlmSettingsModel(**values))
        session.commit()


def _models(monkeypatch, response=None, error=None):
    def get(url, headers=None, timeout=None):
        if error:
            raise error
        return response

    monkeypatch.setattr(settings_routes._requests, "get", get)


def test_disabled_without_endpoint(client, create_user, auth_headers):
    admin = create_user("a1", role="admin")
    assert _llm_status(client, admin, auth_headers) == "disabled"


def test_disabled_when_llm_switched_off(
    client, create_user, auth_headers, session_factory
):
    _configure(session_factory, llm_enabled=False)
    admin = create_user("a2", role="admin")
    assert _llm_status(client, admin, auth_headers) == "disabled"


def test_online_when_model_is_listed(
    client, create_user, auth_headers, session_factory, monkeypatch
):
    _configure(session_factory)
    _models(monkeypatch, FakeResponse(body={"data": [{"id": "qwen"}]}))
    admin = create_user("a3", role="admin")
    assert _llm_status(client, admin, auth_headers) == "online"


def test_online_for_ollama_name_with_tag(
    client, create_user, auth_headers, session_factory, monkeypatch
):
    _configure(session_factory)
    _models(monkeypatch, FakeResponse(body={"data": [{"id": "qwen:latest"}]}))
    admin = create_user("a4", role="admin")
    assert _llm_status(client, admin, auth_headers) == "online"


def test_offline_when_model_is_not_listed(
    client, create_user, auth_headers, session_factory, monkeypatch
):
    _configure(session_factory)
    _models(monkeypatch, FakeResponse(body={"data": [{"id": "other"}]}))
    admin = create_user("a5", role="admin")
    assert _llm_status(client, admin, auth_headers) == "offline"


@pytest.mark.parametrize("status", [401, 403, 502])
def test_offline_on_auth_or_server_error(
    client, create_user, auth_headers, session_factory, monkeypatch, status
):
    _configure(session_factory)
    _models(monkeypatch, FakeResponse(status=status))
    admin = create_user(f"a6-{status}", role="admin")
    assert _llm_status(client, admin, auth_headers) == "offline"


def test_offline_when_unreachable(
    client, create_user, auth_headers, session_factory, monkeypatch
):
    _configure(session_factory)
    _models(monkeypatch, error=requests.exceptions.ConnectionError("down"))
    admin = create_user("a7", role="admin")
    assert _llm_status(client, admin, auth_headers) == "offline"


def test_online_when_server_has_no_model_list(
    client, create_user, auth_headers, session_factory, monkeypatch
):
    _configure(session_factory)
    _models(monkeypatch, FakeResponse(status=404))
    admin = create_user("a8", role="admin")
    assert _llm_status(client, admin, auth_headers) == "online"
