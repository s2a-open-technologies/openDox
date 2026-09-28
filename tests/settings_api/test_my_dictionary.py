"""Tests for GET/PUT /api/v1/settings/my-dictionary/.

The personal dictionary is private per user: no endpoint may expose one
user's glossary to another user, admin or not (see AGENTS.md "Phonetic
Term Correction" — deliberately diverges from the personal-categories
precedent, where admins can see everyone's).
"""

from cryptography.fernet import Fernet
from sqlalchemy import text

from backend.components.security import field_encryption


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


def test_personal_glossary_absent_from_own_profile_endpoint(
    client, create_user, auth_headers
):
    """Regression guard: /auth/me must never leak personal_glossary."""
    user = create_user("alice")
    client.put(
        "/api/v1/settings/my-dictionary/",
        json={"personal_glossary": "Sertralin"},
        headers=auth_headers(user),
    )

    response = client.get("/api/v1/auth/me", headers=auth_headers(user))

    assert "personal_glossary" not in response.json()


def test_personal_glossary_absent_from_admin_user_list(
    client, create_user, auth_headers
):
    """Regression guard: the admin user list must never leak personal_glossary."""
    alice = create_user("alice")
    admin = create_user("admin_user", role="admin")
    client.put(
        "/api/v1/settings/my-dictionary/",
        json={"personal_glossary": "Sertralin"},
        headers=auth_headers(alice),
    )

    response = client.get("/api/v1/auth/users", headers=auth_headers(admin))

    assert response.status_code == 200
    for user in response.json():
        assert "personal_glossary" not in user


def test_personal_glossary_is_encrypted_at_rest(
    client, create_user, auth_headers, session_factory, monkeypatch
):
    monkeypatch.setattr(field_encryption, "_fernet", Fernet(Fernet.generate_key()))
    user = create_user("alice")

    client.put(
        "/api/v1/settings/my-dictionary/",
        json={"personal_glossary": "Dr. Müller, Sertralin"},
        headers=auth_headers(user),
    )

    with session_factory() as session:
        raw = session.execute(
            text("SELECT personal_glossary FROM user WHERE id = :id"),
            {"id": user.id},
        ).scalar_one()

    assert raw != "Dr. Müller, Sertralin"
    assert field_encryption.decrypt(raw) == "Dr. Müller, Sertralin"
