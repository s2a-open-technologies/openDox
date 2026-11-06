"""The built-in "Standard" category is read-only; admins choose the default.

The shipped prompt must not be changed by anyone (docs/zweckbestimmung.md
§6): name, description and system prompt of the ``is_builtin`` category are
locked and it cannot be deleted. An admin/moderator can make any global
category the one preselected for everyone (``is_default``).
"""

import io
import json

from sqlmodel import select

from backend.components.models.audit_model import AuditEvent
from backend.components.models.categories import Categories

URL = "/api/v1/settings/categories/"
PROMPT = "Mitgelieferter Prompt"


def _builtin(session_factory) -> int:
    with session_factory() as session:
        category = Categories(
            name="Standard",
            description="Allgemeine Dokumentation",
            system_prompt=PROMPT,
            is_builtin=True,
        )
        session.add(category)
        session.commit()
        return category.id


def _global(session_factory, name="Kardio") -> int:
    with session_factory() as session:
        category = Categories(name=name, description="d", system_prompt="Eigener")
        session.add(category)
        session.commit()
        return category.id


def _payload(**overrides):
    payload = {
        "name": "Standard",
        "description": "Allgemeine Dokumentation",
        "system_prompt": PROMPT,
    }
    payload.update(overrides)
    return payload


def _admin(create_user, auth_headers):
    return auth_headers(create_user("admin", role="admin"))


def test_builtin_prompt_name_and_description_are_locked(
    client, create_user, auth_headers, session_factory
):
    builtin_id = _builtin(session_factory)
    headers = _admin(create_user, auth_headers)

    for field, value in (
        ("system_prompt", "Neuer Prompt"),
        ("name", "Umbenannt"),
        ("description", "Neu"),
    ):
        response = client.put(
            f"{URL}{builtin_id}", json=_payload(**{field: value}), headers=headers
        )
        assert response.status_code == 403, field
        assert response.json()["detail"]["code"] == "builtin_category_locked"

    with session_factory() as session:
        stored = session.get(Categories, builtin_id)
        assert (stored.name, stored.system_prompt) == ("Standard", PROMPT)


def test_builtin_other_fields_stay_editable(
    client, create_user, auth_headers, session_factory
):
    builtin_id = _builtin(session_factory)
    headers = _admin(create_user, auth_headers)

    response = client.put(
        f"{URL}{builtin_id}",
        json=_payload(whisper_prompt="Ramipril", llm_enabled=False),
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["whisper_prompt"] == "Ramipril"
    assert body["llm_enabled"] is False
    assert body["is_builtin"] is True


def test_builtin_cannot_be_deleted(client, create_user, auth_headers, session_factory):
    builtin_id = _builtin(session_factory)
    headers = _admin(create_user, auth_headers)

    response = client.delete(f"{URL}{builtin_id}", headers=headers)

    assert response.status_code == 403
    with session_factory() as session:
        assert session.get(Categories, builtin_id) is not None


def test_flags_cannot_be_set_through_create_or_update(
    client, create_user, auth_headers, session_factory
):
    headers = _admin(create_user, auth_headers)

    created = client.post(
        URL,
        json={
            "name": "X",
            "description": "d",
            "system_prompt": "p",
            "is_builtin": True,
            "is_default": True,
        },
        headers=headers,
    ).json()
    assert created["is_builtin"] is False
    assert created["is_default"] is False

    updated = client.put(
        f"{URL}{created['id']}",
        json={
            "name": "X",
            "description": "d",
            "system_prompt": "p",
            "is_builtin": True,
        },
        headers=headers,
    ).json()
    assert updated["is_builtin"] is False


def test_set_default_keeps_exactly_one_and_is_audited(
    client, create_user, auth_headers, session_factory
):
    builtin_id = _builtin(session_factory)
    first = _global(session_factory, "Kardio")
    second = _global(session_factory, "Ortho")
    headers = _admin(create_user, auth_headers)

    assert client.put(f"{URL}{first}/default", headers=headers).status_code == 200
    response = client.put(f"{URL}{second}/default", headers=headers)

    assert response.status_code == 200
    assert response.json()["is_default"] is True
    listed = client.get(URL, headers=headers).json()
    assert [c["id"] for c in listed] == [second, builtin_id, first]
    assert [c["id"] for c in listed if c["is_default"]] == [second]
    with session_factory() as session:
        actions = session.exec(
            select(AuditEvent).where(AuditEvent.action == "category.default")
        ).all()
        assert len(actions) == 2


def test_builtin_is_listed_first_without_a_default(
    client, create_user, auth_headers, session_factory
):
    first = _global(session_factory)
    builtin_id = _builtin(session_factory)
    headers = _admin(create_user, auth_headers)

    listed = client.get(URL, headers=headers).json()

    assert [c["id"] for c in listed] == [builtin_id, first]


def test_set_default_requires_privileged_role_and_global_category(
    client, create_user, auth_headers, session_factory, allow_personal_categories
):
    global_id = _global(session_factory)
    user = create_user("dr.a")
    admin = create_user("admin", role="admin")
    personal = client.post(
        URL,
        json={"name": "Meine", "description": "d", "system_prompt": "p"},
        headers=auth_headers(user),
    ).json()["id"]

    assert (
        client.put(f"{URL}{global_id}/default", headers=auth_headers(user)).status_code
        == 403
    )
    # Another user's personal category stays invisible, admins included.
    assert (
        client.put(f"{URL}{personal}/default", headers=auth_headers(admin)).status_code
        == 404
    )
    own = client.post(
        URL,
        json={
            "name": "Admin privat",
            "description": "d",
            "system_prompt": "p",
            "scope": "personal",
        },
        headers=auth_headers(admin),
    ).json()["id"]
    response = client.put(f"{URL}{own}/default", headers=auth_headers(admin))
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "default_must_be_global"


def _restore(client, headers, backup):
    file_bytes = io.BytesIO(json.dumps(backup).encode())
    return client.post(
        "/api/v1/settings/backup/restore/",
        files={"file": ("backup.json", file_bytes, "application/json")},
        headers=headers,
    )


def test_restore_keeps_builtin_prompt_and_default(
    client, create_user, auth_headers, session_factory
):
    builtin_id = _builtin(session_factory)
    custom = _global(session_factory)
    headers = _admin(create_user, auth_headers)
    client.put(f"{URL}{custom}/default", headers=headers)
    backup = client.get("/api/v1/settings/backup/", headers=headers).json()
    for entry in backup["settings"]["categories"]:
        if entry["is_builtin"]:
            entry["system_prompt"] = "Manipuliert"
            entry["whisper_prompt"] = "Ramipril"

    assert _restore(client, headers, backup).status_code == 200

    with session_factory() as session:
        builtin = session.get(Categories, builtin_id)
        assert builtin.system_prompt == PROMPT
        assert builtin.whisper_prompt == "Ramipril"
        rows = session.exec(select(Categories)).all()
        assert [r.name for r in rows if r.is_default] == ["Kardio"]
        assert [r.id for r in rows if r.is_builtin] == [builtin_id]


def test_restore_of_old_backup_maps_allgemein_to_builtin(
    client, create_user, auth_headers, session_factory
):
    builtin_id = _builtin(session_factory)
    headers = _admin(create_user, auth_headers)
    old = {
        "settings": {
            "categories": [
                {
                    "name": "Allgemein",
                    "description": "alt",
                    "system_prompt": "Alter Prompt",
                    "whisper_prompt": "Metformin",
                    "user_id": None,
                    "is_builtin": False,
                },
                {
                    "name": "Fake",
                    "description": "d",
                    "system_prompt": "p",
                    "user_id": None,
                },
            ]
        }
    }

    assert _restore(client, headers, old).status_code == 200

    with session_factory() as session:
        rows = session.exec(select(Categories)).all()
        assert sorted(r.name for r in rows) == ["Fake", "Standard"]
        builtin = session.get(Categories, builtin_id)
        assert builtin.system_prompt == PROMPT
        assert builtin.whisper_prompt == "Metformin"
