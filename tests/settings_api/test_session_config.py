"""Tests for the web UI session policy (session-config)."""


def test_get_session_config_returns_default(client, create_user, auth_headers):
    user = create_user("dr.mueller")

    response = client.get(
        "/api/v1/settings/session-config/", headers=auth_headers(user)
    )

    assert response.status_code == 200
    assert response.json() == {"idle_timeout_minutes": 30}


def test_get_session_config_requires_login(client):
    assert client.get("/api/v1/settings/session-config/").status_code == 401


def test_put_session_config_saves(client, create_user, auth_headers):
    admin = create_user("admin", role="admin")

    response = client.put(
        "/api/v1/settings/session-config/",
        json={"idle_timeout_minutes": 0},
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json() == {"idle_timeout_minutes": 0}
    again = client.get("/api/v1/settings/session-config/", headers=auth_headers(admin))
    assert again.json() == {"idle_timeout_minutes": 0}


def test_put_session_config_rejects_negative(client, create_user, auth_headers):
    admin = create_user("admin", role="admin")

    response = client.put(
        "/api/v1/settings/session-config/",
        json={"idle_timeout_minutes": -5},
        headers=auth_headers(admin),
    )

    assert response.status_code == 422


def test_put_session_config_admin_only(client, create_user, auth_headers):
    for role in ("user", "moderator", "demo_viewer"):
        user = create_user(f"u-{role}", role=role)

        response = client.put(
            "/api/v1/settings/session-config/",
            json={"idle_timeout_minutes": 5},
            headers=auth_headers(user),
        )

        assert response.status_code == 403
