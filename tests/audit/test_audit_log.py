"""Tests for the admin audit log (audit_service + audit_routes)."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from backend.components.models.audit_model import AuditEvent
from backend.components.models.record_model import Record
from backend.components.services.audit_service import (
    add_denied_access_middleware,
    purge_expired,
)

AUDIT = "/api/v1/settings/audit/"
LLM = "/api/v1/settings/llm-settings/"


def _events(session_factory, action=None):
    with session_factory() as session:
        stmt = select(AuditEvent).order_by(AuditEvent.id)
        if action:
            stmt = stmt.where(AuditEvent.action == action)
        return session.exec(stmt).all()


@pytest.fixture
def audited_client(app, session_factory):
    """Client whose app also logs 403 responses, as run.py wires it."""
    add_denied_access_middleware(app, session_factory)
    return TestClient(app)


def test_failed_login_is_logged_successful_login_is_not(
    client, create_user, session_factory
):
    create_user("dr.mueller", password="right-password")

    ok = client.post(
        "/api/v1/auth/login", json={"name": "dr.mueller", "password": "right-password"}
    )
    bad = client.post(
        "/api/v1/auth/login", json={"name": "dr.mueller", "password": "wrong"}
    )

    assert ok.status_code == 200
    assert bad.status_code == 401
    events = _events(session_factory, "auth.login")
    assert len(events) == 1
    assert events[0].outcome == "failure"
    assert events[0].actor_name == "dr.mueller"
    assert events[0].details == {"reason": "invalid_credentials"}
    assert "wrong" not in json.dumps(events[0].model_dump(), default=str)


def test_user_management_is_logged_without_password(
    client, create_user, auth_headers, session_factory
):
    admin = create_user("admin1", role="admin")
    headers = auth_headers(admin)

    created = client.post(
        "/api/v1/auth/users",
        json={"name": "neu", "password": "secret-pw-1", "role": "user"},
        headers=headers,
    )
    user_id = created.json()["id"]
    client.put(
        f"/api/v1/auth/users/{user_id}",
        json={"role": "moderator", "password": "secret-pw-2"},
        headers=headers,
    )
    client.delete(f"/api/v1/auth/users/{user_id}", headers=headers)

    actions = [e.action for e in _events(session_factory)]
    assert actions == ["user.create", "user.update", "user.delete"]
    update = _events(session_factory, "user.update")[0]
    assert update.actor_name == "admin1"
    assert update.target_id == str(user_id)
    assert update.details["fields"] == ["role", "password"]
    assert update.details["role"] == {"from": "user", "to": "moderator"}
    dump = json.dumps([e.model_dump() for e in _events(session_factory)], default=str)
    assert "secret-pw" not in dump


def test_settings_change_logs_field_names_but_no_secret_values(
    client, create_user, auth_headers, session_factory
):
    admin = create_user("admin1", role="admin")
    headers = auth_headers(admin)
    payload = client.get(LLM, headers=headers).json()
    payload.update(llm_api_key="sk-very-secret", llm_model="other-model")

    assert client.put(LLM, json=payload, headers=headers).status_code == 200
    # Saving again without a change adds nothing.
    assert client.put(LLM, json=payload, headers=headers).status_code == 200

    events = _events(session_factory, "settings.llm.update")
    assert len(events) == 1
    assert events[0].details == {"fields": ["llm_api_key", "llm_model"]}
    assert "sk-very-secret" not in json.dumps(events[0].model_dump(), default=str)


def test_backup_export_and_restore_are_logged(
    client, create_user, auth_headers, session_factory
):
    headers = auth_headers(create_user("admin1", role="admin"))

    backup = client.get("/api/v1/settings/backup/", headers=headers)
    client.post(
        "/api/v1/settings/backup/restore/",
        files={"file": ("b.json", backup.content, "application/json")},
        headers=headers,
    )

    actions = [e.action for e in _events(session_factory)]
    assert actions == ["backup.export", "backup.restore"]


def test_only_global_categories_are_logged(
    client, create_user, auth_headers, session_factory
):
    moderator = create_user("mod1", role="moderator")
    user = create_user("dr.mueller")
    body = {"name": "Kardiologie", "description": "Herz", "system_prompt": "x"}

    client.post(
        "/api/v1/settings/categories/", json=body, headers=auth_headers(moderator)
    )
    client.post("/api/v1/settings/categories/", json=body, headers=auth_headers(user))

    events = _events(session_factory, "category.create")
    assert len(events) == 1
    assert events[0].actor_name == "mod1"


def test_denied_request_to_foreign_record_is_logged(
    audited_client, create_user, auth_headers, session_factory
):
    owner = create_user("dr.mueller")
    other = create_user("dr.schmidt")
    with session_factory() as session:
        record = Record(
            session_id="s1",
            user_id=owner.id,
            title="Herr Mustermann",
            content="Befund",
            timestamp="01.01.2026 00:00:00",
            summarize="",
            file="",
        )
        session.add(record)
        session.commit()
        record_id = record.id

    response = audited_client.get(
        f"/api/v1/records/record/{record_id}", headers=auth_headers(other)
    )
    # The owner reading their own record is not logged.
    audited_client.get(
        f"/api/v1/records/record/{record_id}", headers=auth_headers(owner)
    )

    assert response.status_code == 403
    events = _events(session_factory)
    assert [e.action for e in events] == ["access.denied"]
    assert events[0].actor_name == "dr.schmidt"
    assert events[0].outcome == "denied"
    assert events[0].details["path"] == f"/api/v1/records/record/{record_id}"
    assert "Mustermann" not in json.dumps(events[0].model_dump(), default=str)


def test_audit_log_is_admin_only(
    audited_client, create_user, auth_headers, session_factory
):
    moderator = create_user("mod1", role="moderator")

    response = audited_client.get(AUDIT, headers=auth_headers(moderator))

    assert response.status_code == 403
    assert [e.action for e in _events(session_factory)] == ["access.denied"]


def test_audit_view_filters_and_is_not_logged(
    client, create_user, auth_headers, session_factory
):
    admin = create_user("admin1", role="admin")
    headers = auth_headers(admin)
    client.post("/api/v1/auth/login", json={"name": "x", "password": "y"})

    page = client.get(AUDIT, params={"action": "auth."}, headers=headers).json()

    assert page["total"] == 1
    assert page["items"][0]["action"] == "auth.login"
    assert [e.action for e in _events(session_factory)] == ["auth.login"]


def test_csv_export_defuses_formulas(
    client, create_user, auth_headers, session_factory
):
    headers = auth_headers(create_user("admin1", role="admin"))
    client.post("/api/v1/auth/login", json={"name": "=HYPERLINK(1)", "password": "y"})

    response = client.get(f"{AUDIT}export/", headers=headers)

    assert response.status_code == 200
    assert "'=HYPERLINK(1)" in response.text
    assert _events(session_factory)[-1].action == "audit.export"


def test_purge_expired_deletes_only_old_entries(session_factory):
    now = datetime.now(timezone.utc)
    with session_factory() as session:
        session.add(AuditEvent(action="old", timestamp=now - timedelta(days=400)))
        session.add(AuditEvent(action="new", timestamp=now - timedelta(days=10)))
        session.commit()

    assert purge_expired(session_factory, 0) == 0
    assert purge_expired(session_factory, 365) == 1
    assert [e.action for e in _events(session_factory)] == ["new"]
