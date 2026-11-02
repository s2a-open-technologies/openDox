"""Personal categories need the operator's go and are never visible to admins.

A user's own LLM prompt bypasses the operator's control over the intended
purpose (docs/zweckbestimmung.md §6), so ``personal_categories_allowed`` is
off by default — which also neutralises personal categories that already
exist. Independently of it, nobody sees another user's personal category.
"""

from unittest.mock import MagicMock

import backend.components.services.llm_gate as llm_gate
from backend.components.models.audit_model import AuditEvent
from backend.components.models.categories import Categories
from backend.components.models.record_model import Record
from backend.components.services.llm_gate import effective_category

URL = "/api/v1/settings/categories/"
POLICY_URL = "/api/v1/settings/category-policy/"


def _payload(**overrides):
    payload = {"name": "Meine", "description": "d", "system_prompt": "Eigener Prompt"}
    payload.update(overrides)
    return payload


def _personal_category(session_factory, user_id) -> int:
    with session_factory() as session:
        category = Categories(
            name="Meine",
            description="d",
            system_prompt="Eigener Prompt",
            user_id=user_id,
        )
        session.add(category)
        session.commit()
        return category.id


def _record(session_factory, user_id, category_id) -> Record:
    with session_factory() as session:
        record = Record(
            session_id="s",
            user_id=user_id,
            category_id=category_id,
            title="t",
            content="Text.",
            timestamp="01.01.2026 00:00:00",
            summarize="",
            file="",
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def _allow(client, admin_headers, allowed: bool):
    response = client.put(
        POLICY_URL,
        json={"personal_categories_allowed": allowed},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text


def test_policy_is_off_by_default_and_readable_by_everyone(
    client, create_user, auth_headers
):
    user = create_user("dr.a")

    body = client.get(POLICY_URL, headers=auth_headers(user)).json()

    assert body == {"personal_categories_allowed": False}


def test_only_admins_change_the_policy_and_it_is_audited(
    client, create_user, auth_headers, session_factory
):
    user = create_user("dr.a")
    admin = create_user("admin", role="admin")

    denied = client.put(
        POLICY_URL,
        json={"personal_categories_allowed": True},
        headers=auth_headers(user),
    )
    _allow(client, auth_headers(admin), True)

    assert denied.status_code == 403
    with session_factory() as session:
        event = (
            session.query(AuditEvent)
            .filter(AuditEvent.action == "settings.category_policy.update")
            .one()
        )
        assert "personal_categories_allowed" in str(event.details)


def test_user_cannot_create_personal_category_while_off(
    client, create_user, auth_headers
):
    user = create_user("dr.a")

    response = client.post(URL, json=_payload(), headers=auth_headers(user))

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "personal_categories_disabled"


def test_existing_personal_category_is_hidden_and_inert_while_off(
    client, create_user, auth_headers, session_factory
):
    user = create_user("dr.a")
    category_id = _personal_category(session_factory, user.id)

    listed = client.get(URL, headers=auth_headers(user)).json()
    edited = client.put(
        f"{URL}{category_id}", json=_payload(), headers=auth_headers(user)
    )

    assert listed == []
    assert edited.status_code == 403
    with session_factory() as session:
        record = _record(session_factory, user.id, category_id)
        assert effective_category(session, record) is None


def test_personal_prompt_never_reaches_the_llm_while_off(
    session_factory, create_user, monkeypatch
):
    user = create_user("dr.a")
    category_id = _personal_category(session_factory, user.id)
    record = _record(session_factory, user.id, category_id)
    model = MagicMock()
    model.generate_response.return_value = "x"
    monkeypatch.setattr(llm_gate, "SummarizeModel", lambda *a, **k: model)

    with session_factory() as session:
        llm_gate.run_summary(session, effective_category(session, record), "Text.")

    assert model.generate_response.call_args.kwargs["custom_system_prompt"] is None


def test_personal_category_works_once_allowed(
    client, create_user, auth_headers, session_factory
):
    user = create_user("dr.a")
    admin = create_user("admin", role="admin")
    _allow(client, auth_headers(admin), True)

    created = client.post(URL, json=_payload(), headers=auth_headers(user))

    assert created.status_code == 200, created.text
    assert [c["name"] for c in client.get(URL, headers=auth_headers(user)).json()] == [
        "Meine"
    ]
    with session_factory() as session:
        record = _record(session_factory, user.id, created.json()["id"])
        assert effective_category(session, record).system_prompt == "Eigener Prompt"


def test_admin_never_sees_another_users_personal_category(
    client, create_user, auth_headers, session_factory
):
    user = create_user("dr.a")
    admin = create_user("admin", role="admin")
    _allow(client, auth_headers(admin), True)
    category_id = _personal_category(session_factory, user.id)
    headers = auth_headers(admin)

    listed = client.get(URL, headers=headers).json()

    assert category_id not in [c["id"] for c in listed]
    assert client.get(f"{URL}{category_id}", headers=headers).status_code == 404
    assert (
        client.put(f"{URL}{category_id}", json=_payload(), headers=headers).status_code
        == 404
    )
    assert client.delete(f"{URL}{category_id}", headers=headers).status_code == 404


def test_record_cannot_be_moved_into_a_disabled_personal_category(
    client, create_user, auth_headers, session_factory
):
    user = create_user("dr.a")
    category_id = _personal_category(session_factory, user.id)
    record = _record(session_factory, user.id, None)

    response = client.put(
        f"/api/v1/records/record/{record.id}",
        json={"category_id": category_id},
        headers=auth_headers(user),
    )

    assert response.status_code == 404
