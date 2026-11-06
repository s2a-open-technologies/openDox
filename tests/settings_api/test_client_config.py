"""Tests for the desktop-client endpoints (client-config, client-distribution)."""

import httpx
import pytest

from backend.components.services import client_release

DEFAULT_CONFIG = {
    "clipboard_exclude_from_history": True,
    "clipboard_clear_after_seconds": 30,
    "insert_allowlist": [],
    "dictation_mic_mode": "hold",
    "live_view": True,
}


@pytest.fixture(autouse=True)
def _no_github(monkeypatch):
    """Keep tests offline: the release lookup is disabled unless a test enables it."""
    client_release.reset_cache()
    monkeypatch.setenv("CLIENT_LATEST_RELEASE_URL", "")
    yield
    client_release.reset_cache()


def _mock_github(monkeypatch, handler):
    monkeypatch.setenv("CLIENT_LATEST_RELEASE_URL", "https://github.test/latest")
    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(client_release.httpx, "AsyncClient", fake_client)


def test_get_client_config_is_public_and_returns_defaults(client):
    response = client.get("/api/v1/settings/client-config/")

    assert response.status_code == 200
    assert response.json() == {**DEFAULT_CONFIG, "latest_client_version": None}


def test_get_client_config_reports_latest_client_version(client, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request.url)
        return httpx.Response(200, json={"tag_name": "v0.9.1"})

    _mock_github(monkeypatch, handler)

    first = client.get("/api/v1/settings/client-config/").json()
    second = client.get("/api/v1/settings/client-config/").json()

    assert first["latest_client_version"] == "0.9.1"
    assert second["latest_client_version"] == "0.9.1"
    assert len(calls) == 1  # cached


def test_get_client_config_survives_github_failure(client, monkeypatch):
    _mock_github(monkeypatch, lambda request: httpx.Response(503))

    response = client.get("/api/v1/settings/client-config/")

    assert response.status_code == 200
    assert response.json() == {**DEFAULT_CONFIG, "latest_client_version": None}


def test_put_client_config_saves_and_normalizes(client, create_user, auth_headers):
    admin = create_user("admin", role="admin")

    response = client.put(
        "/api/v1/settings/client-config/",
        json={
            "clipboard_exclude_from_history": False,
            "clipboard_clear_after_seconds": 0,
            "insert_allowlist": [" Notepad.exe ", "", "medistar", "notepad.exe"],
            "dictation_mic_mode": "toggle",
            "live_view": False,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    expected = {
        "clipboard_exclude_from_history": False,
        "clipboard_clear_after_seconds": 0,
        "insert_allowlist": ["Notepad.exe", "medistar"],
        "dictation_mic_mode": "toggle",
        "live_view": False,
    }
    assert response.json() == expected
    assert client.get("/api/v1/settings/client-config/").json() == {
        **expected,
        "latest_client_version": None,
    }


def test_put_client_config_requires_admin(client, create_user, auth_headers):
    user = create_user("alice")

    response = client.put(
        "/api/v1/settings/client-config/",
        json=DEFAULT_CONFIG,
        headers=auth_headers(user),
    )

    assert response.status_code == 403


def test_put_client_config_requires_auth(client):
    response = client.put("/api/v1/settings/client-config/", json=DEFAULT_CONFIG)

    assert response.status_code in (401, 403)


def test_put_client_config_rejects_unknown_mic_mode(client, create_user, auth_headers):
    admin = create_user("admin", role="admin")

    response = client.put(
        "/api/v1/settings/client-config/",
        json={**DEFAULT_CONFIG, "dictation_mic_mode": "sometimes"},
        headers=auth_headers(admin),
    )

    assert response.status_code == 422


def test_put_client_config_rejects_negative_clear_delay(
    client, create_user, auth_headers
):
    admin = create_user("admin", role="admin")

    response = client.put(
        "/api/v1/settings/client-config/",
        json={**DEFAULT_CONFIG, "clipboard_clear_after_seconds": -1},
        headers=auth_headers(admin),
    )

    assert response.status_code == 422


def test_client_distribution_derives_server_url(
    client, create_user, auth_headers, monkeypatch
):
    monkeypatch.delenv("CLIENT_SERVER_URL", raising=False)
    monkeypatch.setenv("ROOT_PATH", "/opendox")
    admin = create_user("admin", role="admin")

    response = client.get(
        "/api/v1/settings/client-distribution/", headers=auth_headers(admin)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["server_url"] == "http://testserver/opendox"
    assert body["download_base_url"].endswith("/releases/latest/download")
    assert body["files"]["windows_msi"] == "opendox-client-installer.msi"


def test_client_distribution_prefers_configured_urls(
    client, create_user, auth_headers, monkeypatch
):
    monkeypatch.setenv("CLIENT_SERVER_URL", "https://dox.klinik.de/")
    monkeypatch.setenv("CLIENT_DOWNLOAD_BASE_URL", "https://files.klinik.de/opendox/")
    admin = create_user("admin", role="admin")

    body = client.get(
        "/api/v1/settings/client-distribution/", headers=auth_headers(admin)
    ).json()

    assert body["server_url"] == "https://dox.klinik.de"
    assert body["download_base_url"] == "https://files.klinik.de/opendox"


def test_client_distribution_requires_admin(client, create_user, auth_headers):
    user = create_user("alice")

    response = client.get(
        "/api/v1/settings/client-distribution/", headers=auth_headers(user)
    )

    assert response.status_code == 403
