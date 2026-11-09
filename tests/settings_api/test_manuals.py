"""Tests for the manual download links (GET /settings/manuals/)."""

import pytest

URL = "/api/v1/settings/manuals/"


@pytest.fixture(autouse=True)
def _version(app, monkeypatch):
    monkeypatch.setattr(app, "version", "1.2.3")
    monkeypatch.delenv("MANUALS_DOWNLOAD_BASE_URL", raising=False)


def test_admin_gets_release_links(client, create_user, auth_headers):
    admin = create_user("admin", role="admin")

    response = client.get(URL, headers=auth_headers(admin))

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "1.2.3"
    assert body["release_url"] == (
        "https://github.com/s2a-open-technologies/openDox/releases/tag/v1.2.3"
    )
    base = "https://github.com/s2a-open-technologies/openDox/releases/download/v1.2.3"
    assert body["manuals"] == [
        {
            "key": "benutzer",
            "file": "openDox-Benutzerhandbuch-1.2.3.pdf",
            "url": f"{base}/openDox-Benutzerhandbuch-1.2.3.pdf",
        },
        {
            "key": "administration",
            "file": "openDox-Administrationshandbuch-1.2.3.pdf",
            "url": f"{base}/openDox-Administrationshandbuch-1.2.3.pdf",
        },
        {
            "key": "installation",
            "file": "openDox-Installationshandbuch-1.2.3.pdf",
            "url": f"{base}/openDox-Installationshandbuch-1.2.3.pdf",
        },
    ]


def test_demo_viewer_may_read(client, create_user, auth_headers):
    viewer = create_user("viewer", role="demo_viewer")

    assert client.get(URL, headers=auth_headers(viewer)).status_code == 200


@pytest.mark.parametrize("role", ["user", "moderator"])
def test_other_roles_are_refused(client, create_user, auth_headers, role):
    user = create_user("someone", role=role)

    response = client.get(URL, headers=auth_headers(user))

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "admin_required"


def test_base_url_override(client, create_user, auth_headers, monkeypatch):
    monkeypatch.setenv("MANUALS_DOWNLOAD_BASE_URL", "https://mirror.local/v{version}/")
    admin = create_user("admin", role="admin")

    manuals = client.get(URL, headers=auth_headers(admin)).json()["manuals"]

    assert manuals[0]["url"] == (
        "https://mirror.local/v1.2.3/openDox-Benutzerhandbuch-1.2.3.pdf"
    )


def test_unknown_version_has_no_links(client, create_user, auth_headers, app):
    app.version = "unknown"
    admin = create_user("admin", role="admin")

    body = client.get(URL, headers=auth_headers(admin)).json()

    assert body["manuals"] == []
