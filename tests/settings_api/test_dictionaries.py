"""Tests for the /api/v1/settings/dictionaries/ endpoints.

Personal dictionaries are private per user — no endpoint exposes one to
another user, admins included (unlike personal categories). Global ones are
managed by admins/moderators and readable by everyone.
"""

from cryptography.fernet import Fernet
from sqlalchemy import text

from backend.components.security import field_encryption

BASE = "/api/v1/settings/dictionaries/"


def _create(client, headers, name="Test", scope="personal", terms=None):
    response = client.post(
        BASE, json={"name": name, "scope": scope, "terms": terms or []}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_create_personal_dictionary_normalizes_terms(client, create_user, auth_headers):
    alice = create_user("alice")

    body = _create(
        client,
        auth_headers(alice),
        terms=[
            "  Sertralin ",
            "sertralin",
            "",
            "# Kommentar",
            "Hypertonie, essentiell",
        ],
    )

    assert body["user_id"] == alice.id
    assert body["terms"] == ["Sertralin", "Hypertonie, essentiell"]
    assert body["term_count"] == 2


def test_user_cannot_create_global_dictionary(client, create_user, auth_headers):
    alice = create_user("alice")

    response = client.post(
        BASE, json={"name": "ICD", "scope": "global"}, headers=auth_headers(alice)
    )

    assert response.status_code == 403


def test_moderator_creates_global_dictionary_visible_to_all(
    client, create_user, auth_headers
):
    mod = create_user("mod", role="moderator")
    alice = create_user("alice")
    created = _create(client, auth_headers(mod), name="ICD", scope="global")

    listing = client.get(BASE, headers=auth_headers(alice)).json()

    assert created["user_id"] is None
    assert [d["name"] for d in listing] == ["ICD"]
    assert "terms" not in listing[0]


def test_personal_dictionary_is_private_even_from_admin(
    client, create_user, auth_headers
):
    alice = create_user("alice")
    admin = create_user("admin1", role="admin")
    bob = create_user("bob")
    created = _create(client, auth_headers(alice), terms=["Alice-only"])

    for other in (admin, bob):
        headers = auth_headers(other)
        assert client.get(BASE, headers=headers).json() == []
        assert client.get(f"{BASE}{created['id']}", headers=headers).status_code == 404
        put = client.put(f"{BASE}{created['id']}", json={"name": "x"}, headers=headers)
        assert put.status_code == 404


def test_user_cannot_change_global_dictionary(client, create_user, auth_headers):
    mod = create_user("mod", role="moderator")
    alice = create_user("alice")
    created = _create(client, auth_headers(mod), scope="global")

    response = client.put(
        f"{BASE}{created['id']}", json={"terms": ["x"]}, headers=auth_headers(alice)
    )

    assert response.status_code == 403


def test_update_replaces_terms_and_renames(client, create_user, auth_headers):
    alice = create_user("alice")
    headers = auth_headers(alice)
    created = _create(client, headers, terms=["Alt"])

    response = client.put(
        f"{BASE}{created['id']}",
        json={"name": "Neu", "terms": ["Metformin", "Ibuprofen"]},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Neu"
    assert response.json()["terms"] == ["Metformin", "Ibuprofen"]
    assert response.json()["term_count"] == 2


def test_upload_txt_replace_and_append(client, create_user, auth_headers):
    alice = create_user("alice")
    headers = auth_headers(alice)
    created = _create(client, headers, terms=["Alt"])
    url = f"{BASE}{created['id']}/upload"

    replaced = client.post(
        url,
        files={"file": ("liste.txt", "﻿# Kopf\nSertralin\n\nMetformin\n".encode())},
        data={"mode": "replace"},
        headers=headers,
    )
    appended = client.post(
        url,
        files={"file": ("mehr.txt", b"Ibuprofen\nsertralin\n")},
        data={"mode": "append"},
        headers=headers,
    )

    assert replaced.json()["term_count"] == 2
    assert appended.json()["term_count"] == 3
    terms = client.get(f"{BASE}{created['id']}", headers=headers).json()["terms"]
    assert terms == ["Sertralin", "Metformin", "Ibuprofen"]


def test_upload_csv_uses_first_column_and_keeps_commas(
    client, create_user, auth_headers
):
    alice = create_user("alice")
    headers = auth_headers(alice)
    created = _create(client, headers)
    csv_data = (
        "# Text;Code\n"
        '"Essentielle (primäre) Hypertonie, ohne Angabe";I10.90\n'
        "Diabetes mellitus, Typ 2;E11.9\n"
    ).encode()

    response = client.post(
        f"{BASE}{created['id']}/upload",
        files={"file": ("icd.csv", csv_data)},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    terms = client.get(f"{BASE}{created['id']}", headers=headers).json()["terms"]
    assert terms == [
        "Essentielle (primäre) Hypertonie, ohne Angabe",
        "Diabetes mellitus, Typ 2",
    ]


def test_upload_rejects_other_file_types(client, create_user, auth_headers):
    alice = create_user("alice")
    headers = auth_headers(alice)
    created = _create(client, headers)

    response = client.post(
        f"{BASE}{created['id']}/upload",
        files={"file": ("liste.docx", b"x")},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "dictionary_upload_invalid"


def test_too_long_term_is_rejected(client, create_user, auth_headers):
    alice = create_user("alice")

    response = client.post(
        BASE,
        json={"name": "x", "terms": ["a" * 201]},
        headers=auth_headers(alice),
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "dictionary_term_too_long"


def test_delete_detaches_from_categories(client, create_user, auth_headers):
    alice = create_user("alice")
    headers = auth_headers(alice)
    created = _create(client, headers)
    category = client.post(
        "/api/v1/settings/categories/",
        json={
            "name": "Meine",
            "description": "d",
            "system_prompt": "s",
            "dictionary_ids": [created["id"]],
        },
        headers=headers,
    ).json()

    assert client.delete(f"{BASE}{created['id']}", headers=headers).status_code == 200

    reread = client.get(
        f"/api/v1/settings/categories/{category['id']}", headers=headers
    ).json()
    assert reread["dictionary_ids"] == []


def test_dictionary_terms_are_encrypted_at_rest(
    client, create_user, auth_headers, session_factory, monkeypatch
):
    monkeypatch.setattr(field_encryption, "_fernet", Fernet(Fernet.generate_key()))
    alice = create_user("alice")
    created = _create(client, auth_headers(alice), terms=["Dr. Müller"])

    with session_factory() as session:
        raw = session.execute(
            text("SELECT terms FROM dictionary WHERE id = :id"), {"id": created["id"]}
        ).scalar_one()

    assert raw != "Dr. Müller"
    assert field_encryption.decrypt(raw) == "Dr. Müller"
