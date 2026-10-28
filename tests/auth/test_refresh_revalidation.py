"""Tests for re-checking the account when a session is renewed (/auth/refresh)."""

import pytest

from backend.components.models.ldap_model import LdapSettingsModel
from backend.components.models.oidc_model import OidcSettingsModel
from backend.components.models.user_model import User
from backend.components.security.hashing import (
    create_access_token,
    create_refresh_token,
)
from backend.components.services import session_revalidation


def _refresh(client, user_id):
    return client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": create_refresh_token(sub=str(user_id))},
    )


def test_refresh_accepts_legacy_query_parameter(client, create_user):
    user = create_user("dr.mueller")

    response = client.post(
        "/api/v1/auth/refresh",
        params={"refresh_token": create_refresh_token(sub=str(user.id))},
    )

    assert response.status_code == 200


def test_refresh_without_token_is_rejected(client):
    assert client.post("/api/v1/auth/refresh").status_code == 401


def _update_user(session_factory, user_id, **fields):
    with session_factory() as session:
        user = session.get(User, user_id)
        for key, value in fields.items():
            setattr(user, key, value)
        session.add(user)
        session.commit()


def _role(session_factory, user_id):
    with session_factory() as session:
        return session.get(User, user_id).role


@pytest.fixture
def ldap_configured(session_factory):
    with session_factory() as session:
        session.add(
            LdapSettingsModel(
                server_host="ldap.example.com",
                server_port=389,
                base_dn="dc=example,dc=com",
                user_dn="uid",
                bind_user_dn="cn=svc,dc=example,dc=com",
                allowed_groups="opendox",
            )
        )
        session.commit()


@pytest.fixture
def oidc_configured(session_factory):
    def configure(enabled=True):
        with session_factory() as session:
            session.add(OidcSettingsModel(enabled=enabled, allowed_groups="opendox"))
            session.commit()

    return configure


@pytest.fixture
def ldap_answer(monkeypatch):
    def install(result):
        monkeypatch.setattr(
            session_revalidation.LdapService,
            "check_user",
            lambda self, username: result,
        )

    return install


@pytest.fixture
def oidc_answer(monkeypatch):
    calls = []

    def install(result):
        def fake_refresh(self, refresh_token):
            calls.append(refresh_token)
            return result

        monkeypatch.setattr(session_revalidation.OidcService, "refresh", fake_refresh)
        return calls

    return install


def test_refresh_rejects_inactive_user(client, create_user, session_factory):
    user = create_user("dr.mueller")
    _update_user(session_factory, user.id, is_active=False)

    assert _refresh(client, user.id).status_code == 401


def test_refresh_rejects_deleted_user(client):
    assert _refresh(client, 9999).status_code == 401


def test_refresh_rejects_access_token(client, create_user):
    user = create_user("dr.mueller")

    response = client.post(
        "/api/v1/auth/refresh",
        params={"refresh_token": create_access_token(sub=str(user.id))},
    )

    assert response.status_code == 401


def test_refresh_ldap_user_gets_current_role(
    client, create_user, session_factory, ldap_configured, ldap_answer
):
    user = create_user("jdoe")
    _update_user(session_factory, user.id, auth_source="ldap", hashed_password="")
    ldap_answer({"status": "ok", "role": "moderator"})

    assert _refresh(client, user.id).status_code == 200
    assert _role(session_factory, user.id) == "moderator"


def test_refresh_ldap_user_denied(
    client, create_user, session_factory, ldap_configured, ldap_answer
):
    user = create_user("jdoe")
    _update_user(session_factory, user.id, auth_source="ldap", hashed_password="")
    ldap_answer({"status": "denied", "message": "User not found"})

    assert _refresh(client, user.id).status_code == 401


def test_refresh_ldap_unreachable_keeps_session(
    client, create_user, session_factory, ldap_configured, ldap_answer
):
    user = create_user("jdoe", role="moderator")
    _update_user(session_factory, user.id, auth_source="ldap", hashed_password="")
    ldap_answer({"status": "unavailable", "message": "connection refused"})

    assert _refresh(client, user.id).status_code == 200
    assert _role(session_factory, user.id) == "moderator"


def test_refresh_ldap_user_denied_when_ldap_removed(
    client, create_user, session_factory
):
    user = create_user("jdoe")
    _update_user(session_factory, user.id, auth_source="ldap", hashed_password="")

    assert _refresh(client, user.id).status_code == 401


def test_refresh_oidc_user_renews_at_provider(
    client, create_user, session_factory, oidc_configured, oidc_answer
):
    oidc_configured()
    user = create_user("jdoe")
    _update_user(
        session_factory, user.id, auth_source="oidc", idp_refresh_token="idp-old"
    )
    calls = oidc_answer({"status": "ok", "role": "admin", "refresh_token": "idp-new"})

    assert _refresh(client, user.id).status_code == 200
    assert calls == ["idp-old"]
    with session_factory() as session:
        stored = session.get(User, user.id)
        assert stored.role == "admin"
        assert stored.idp_refresh_token == "idp-new"


def test_refresh_oidc_user_denied(
    client, create_user, session_factory, oidc_configured, oidc_answer
):
    oidc_configured()
    user = create_user("jdoe")
    _update_user(session_factory, user.id, auth_source="oidc", idp_refresh_token="t")
    oidc_answer({"status": "denied", "message": "invalid_grant"})

    assert _refresh(client, user.id).status_code == 401


def test_refresh_oidc_without_provider_token_keeps_session(
    client, create_user, session_factory, oidc_configured, oidc_answer
):
    oidc_configured()
    user = create_user("jdoe")
    _update_user(session_factory, user.id, auth_source="oidc")
    calls = oidc_answer({"status": "denied", "message": "must not be asked"})

    assert _refresh(client, user.id).status_code == 200
    assert calls == []


def test_refresh_oidc_user_denied_when_oidc_disabled(
    client, create_user, session_factory, oidc_configured
):
    oidc_configured(enabled=False)
    user = create_user("jdoe")
    _update_user(session_factory, user.id, auth_source="oidc", idp_refresh_token="t")

    assert _refresh(client, user.id).status_code == 401


def test_local_login_marks_user_local(client, create_user, session_factory):
    user = create_user("dr.mueller", password="s3cret!")

    client.post(
        "/api/v1/auth/login", json={"name": "dr.mueller", "password": "s3cret!"}
    )

    with session_factory() as session:
        assert session.get(User, user.id).auth_source == "local"


def test_login_of_locked_local_user_is_refused(client, create_user, session_factory):
    user = create_user("dr.mueller", password="s3cret!")
    _update_user(session_factory, user.id, is_active=False)

    response = client.post(
        "/api/v1/auth/login", json={"name": "dr.mueller", "password": "s3cret!"}
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "account_locked"


def test_locked_user_with_wrong_password_gets_no_lock_hint(
    client, create_user, session_factory
):
    user = create_user("dr.mueller", password="s3cret!")
    _update_user(session_factory, user.id, is_active=False)

    response = client.post(
        "/api/v1/auth/login", json={"name": "dr.mueller", "password": "wrong"}
    )

    assert response.status_code == 401


def test_ldap_login_does_not_undo_admin_lock(
    client, create_user, session_factory, ldap_configured, monkeypatch
):
    from backend.views.auth_api import auth_routes

    user = create_user("ldap.user")
    _update_user(session_factory, user.id, hashed_password="", is_active=False)
    monkeypatch.setattr(
        auth_routes.LdapService,
        "authenticate",
        lambda self, username, password: {"success": True, "role": "user"},
    )

    response = client.post(
        "/api/v1/auth/login", json={"name": "ldap.user", "password": "pw"}
    )

    assert response.status_code == 403
    with session_factory() as session:
        assert session.get(User, user.id).is_active is False
