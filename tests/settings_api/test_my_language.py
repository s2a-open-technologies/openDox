"""Tests for GET/PUT /api/v1/settings/my-language/ (per-user UI language)."""


def test_get_my_language_defaults_to_none(client, create_user, auth_headers):
    user = create_user("alice")

    response = client.get("/api/v1/settings/my-language/", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json() == {"ui_language": None}


def test_put_my_language_saves_and_is_returned_by_me(client, create_user, auth_headers):
    user = create_user("alice")
    headers = auth_headers(user)

    response = client.put(
        "/api/v1/settings/my-language/", json={"ui_language": "en"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json() == {"ui_language": "en"}
    assert client.get("/api/v1/auth/me", headers=headers).json()["ui_language"] == "en"


def test_put_my_language_rejects_unsupported_code(client, create_user, auth_headers):
    user = create_user("alice")

    response = client.put(
        "/api/v1/settings/my-language/",
        json={"ui_language": "xx"},
        headers=auth_headers(user),
    )

    assert response.status_code == 422


def test_my_language_is_per_user(client, create_user, auth_headers):
    alice = create_user("alice")
    bob = create_user("bob")

    client.put(
        "/api/v1/settings/my-language/",
        json={"ui_language": "en"},
        headers=auth_headers(alice),
    )

    response = client.get("/api/v1/settings/my-language/", headers=auth_headers(bob))
    assert response.json() == {"ui_language": None}


def test_my_language_requires_auth(client):
    response = client.get("/api/v1/settings/my-language/")

    assert response.status_code in (401, 403)
