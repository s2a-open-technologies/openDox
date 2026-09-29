"""Tests for translatable API errors (code + message + params in `detail`)."""

import io
import json

from backend.components.modules.api_errors import api_error


def test_api_error_builds_structured_detail():
    exc = api_error(422, "audio_format_invalid", "Fallback text", allowed="mp3, ogg")

    assert exc.status_code == 422
    assert exc.detail == {
        "code": "audio_format_invalid",
        "message": "Fallback text",
        "params": {"allowed": "mp3, ogg"},
    }


def test_invalid_backup_format_returns_error_code(client, create_user, auth_headers):
    admin = create_user("admin_user", role="admin")

    response = client.post(
        "/api/v1/settings/backup/restore/",
        files={
            "file": ("b.json", io.BytesIO(json.dumps({}).encode()), "application/json")
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "backup_invalid_format"


def test_invalid_backup_json_returns_error_code_with_params(
    client, create_user, auth_headers
):
    admin = create_user("admin_user", role="admin")

    response = client.post(
        "/api/v1/settings/backup/restore/",
        files={"file": ("b.json", io.BytesIO(b"{not json"), "application/json")},
        headers=auth_headers(admin),
    )

    detail = response.json()["detail"]
    assert response.status_code == 400
    assert detail["code"] == "backup_invalid_json"
    assert detail["params"]["error"]


def test_duplicate_user_returns_error_code(client, create_user, auth_headers):
    admin = create_user("admin_user", role="admin")
    create_user("dup")

    response = client.post(
        "/api/v1/auth/users",
        json={"name": "dup", "password": "pw123456", "role": "user"},
        headers=auth_headers(admin),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "user_exists"


def test_admin_cannot_delete_self_returns_error_code(client, create_user, auth_headers):
    admin = create_user("admin_user", role="admin")

    response = client.delete(
        f"/api/v1/auth/users/{admin.id}", headers=auth_headers(admin)
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "cannot_delete_self"


def test_non_admin_settings_write_returns_admin_required_code(
    client, create_user, auth_headers
):
    user = create_user("alice")

    response = client.put(
        "/api/v1/settings/audio-settings/",
        json={"auto_archive_days": 30},
        headers=auth_headers(user),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "admin_required"


def test_invalid_auto_archive_days_returns_error_code(
    client, create_user, auth_headers
):
    admin = create_user("admin_user", role="admin")

    response = client.put(
        "/api/v1/settings/audio-settings/",
        json={"auto_archive_days": 99999},
        headers=auth_headers(admin),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "auto_archive_days_invalid"
