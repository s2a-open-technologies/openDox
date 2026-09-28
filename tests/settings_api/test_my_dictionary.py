"""Tests for GET/PUT /api/v1/settings/my-dictionary/.

The personal dictionary is private per user: no endpoint may expose one
user's glossary to another user, admin or not (see AGENTS.md "Phonetic
Term Correction" — deliberately diverges from the personal-categories
precedent, where admins can see everyone's).
"""


def test_get_my_dictionary_defaults_to_none(client, create_user, auth_headers):
    user = create_user("alice")
    headers = auth_headers(user)

    response = client.get("/api/v1/settings/my-dictionary/", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"personal_glossary": None}


def test_put_my_dictionary_saves_and_returns_it(client, create_user, auth_headers):
    user = create_user("alice")
    headers = auth_headers(user)

    response = client.put(
        "/api/v1/settings/my-dictionary/",
        json={"personal_glossary": "Sertralin, Ibuprofen"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {"personal_glossary": "Sertralin, Ibuprofen"}

    # Persisted — a fresh GET sees it too.
    get_response = client.get("/api/v1/settings/my-dictionary/", headers=headers)
    assert get_response.json() == {"personal_glossary": "Sertralin, Ibuprofen"}


def test_my_dictionary_is_private_per_user(client, create_user, auth_headers):
    alice = create_user("alice")
    bob = create_user("bob")

    client.put(
        "/api/v1/settings/my-dictionary/",
        json={"personal_glossary": "Alice-only term"},
        headers=auth_headers(alice),
    )

    bob_response = client.get(
        "/api/v1/settings/my-dictionary/", headers=auth_headers(bob)
    )

    assert bob_response.json() == {"personal_glossary": None}


def test_my_dictionary_is_private_from_admin(client, create_user, auth_headers):
    alice = create_user("alice")
    admin = create_user("admin_user", role="admin")

    client.put(
        "/api/v1/settings/my-dictionary/",
        json={"personal_glossary": "Alice-only term"},
        headers=auth_headers(alice),
    )

    admin_response = client.get(
        "/api/v1/settings/my-dictionary/", headers=auth_headers(admin)
    )

    # The admin endpoint only ever returns the caller's OWN dictionary —
    # there is no route that exposes another user's personal_glossary.
    assert admin_response.json() == {"personal_glossary": None}


def test_my_dictionary_requires_auth(client):
    response = client.get("/api/v1/settings/my-dictionary/")

    assert response.status_code in (401, 403)
