"""Tests for the update hint (GET /settings/update-check/)."""

import pytest

from backend.components.services import app_release

URL = "/api/v1/settings/update-check/"
REPO = "https://github.com/s2a-open-technologies/openDox/releases"


@pytest.fixture(autouse=True)
def _setup(app, monkeypatch):
    monkeypatch.setattr(app, "version", "0.12.0")
    monkeypatch.delenv("OPENDOX_LATEST_RELEASE_URL", raising=False)
    app_release.reset_cache()
    yield
    app_release.reset_cache()


def _latest(monkeypatch, version):
    async def fake():
        return version

    monkeypatch.setattr(app_release, "latest_version", fake)


def test_newer_release_is_reported(client, create_user, auth_headers, monkeypatch):
    _latest(monkeypatch, "0.13.0")
    admin = create_user("admin", role="admin")

    body = client.get(URL, headers=auth_headers(admin)).json()

    assert body == {
        "current": "0.12.0",
        "latest": "0.13.0",
        "update_available": True,
        "release_url": f"{REPO}/tag/v0.13.0",
    }


@pytest.mark.parametrize("latest", ["0.12.0", "0.11.9", None])
def test_no_hint_unless_newer(client, create_user, auth_headers, monkeypatch, latest):
    _latest(monkeypatch, latest)
    admin = create_user("admin", role="admin")

    body = client.get(URL, headers=auth_headers(admin)).json()

    assert body["update_available"] is False
    assert body["release_url"] == REPO


def test_demo_viewer_may_read(client, create_user, auth_headers, monkeypatch):
    _latest(monkeypatch, None)
    viewer = create_user("viewer", role="demo_viewer")

    assert client.get(URL, headers=auth_headers(viewer)).status_code == 200


@pytest.mark.parametrize("role", ["user", "moderator"])
def test_other_roles_forbidden(client, create_user, auth_headers, role):
    user = create_user("someone", role=role)

    assert client.get(URL, headers=auth_headers(user)).status_code == 403


def test_requires_login(client):
    assert client.get(URL).status_code in (401, 403)


def test_disabled_by_empty_url(monkeypatch):
    import asyncio

    monkeypatch.setenv("OPENDOX_LATEST_RELEASE_URL", "")

    assert asyncio.run(app_release.latest_version()) is None


def test_version_compare():
    assert app_release.is_newer("0.12.1", "0.12.0")
    assert app_release.is_newer("v1.0", "0.99.9")
    assert not app_release.is_newer("0.12", "0.12.0")
    assert not app_release.is_newer("garbage", "0.12.0")
    assert not app_release.is_newer("0.13.0", "unknown")
