"""Tests for backend.views.auth_api.auth_routes login/token endpoints."""

from backend.components.security.hashing import create_refresh_token


def test_login_with_correct_credentials_returns_tokens(client, create_user):
    create_user("dr.mueller", password="s3cret!")

    response = client.post(
        "/api/v1/auth/login", json={"name": "dr.mueller", "password": "s3cret!"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]


def test_login_with_wrong_password_returns_401(client, create_user):
    create_user("dr.mueller", password="s3cret!")

    response = client.post(
        "/api/v1/auth/login", json={"name": "dr.mueller", "password": "wrong"}
    )

    assert response.status_code == 401


def test_login_with_unknown_user_returns_401(client):
    response = client.post(
        "/api/v1/auth/login", json={"name": "nobody", "password": "whatever"}
    )

    assert response.status_code == 401


def test_me_with_valid_token_returns_user(client, create_user, auth_headers):
    user = create_user("dr.mueller")

    response = client.get("/api/v1/auth/me", headers=auth_headers(user))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user.id
    assert body["name"] == "dr.mueller"
    assert body["role"] == "user"


def test_me_without_authorization_header_is_rejected(client):
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_me_with_refresh_token_as_bearer_is_rejected(client, create_user):
    user = create_user("dr.mueller")
    refresh_token = create_refresh_token(sub=str(user.id))

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh_token}"}
    )

    assert response.status_code == 401


def test_refresh_with_valid_refresh_token_returns_new_tokens(client, create_user):
    user = create_user("dr.mueller")
    refresh_token = create_refresh_token(sub=str(user.id))

    response = client.post(
        "/api/v1/auth/refresh", params={"refresh_token": refresh_token}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
