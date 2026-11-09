"""An LDAP/OIDC login into a same-named local account drops its local password."""

from sqlmodel import select

from backend.components.models.audit_model import AuditEvent
from backend.components.models.ldap_model import LdapSettingsModel
from backend.components.models.user_model import User
from backend.components.services.ldap import LdapService


def _enable_ldap(session_factory, monkeypatch, *, role="user"):
    with session_factory() as session:
        session.add(
            LdapSettingsModel(
                server_host="ldap.example.com",
                server_port=389,
                base_dn="dc=example,dc=com",
                user_dn="uid",
                allowed_groups="opendox",
            )
        )
        session.commit()
    monkeypatch.setattr(
        LdapService,
        "authenticate",
        lambda self, username, password: (
            {"success": True, "message": "ok", "role": role}
            if password == "ldap-pass"
            else {"success": False, "message": "Invalid credentials"}
        ),
    )


def _events(session_factory, action):
    with session_factory() as session:
        return session.exec(select(AuditEvent).where(AuditEvent.action == action)).all()


def _login(client, name, password):
    return client.post("/api/v1/auth/login", json={"name": name, "password": password})


def test_ldap_takeover_removes_local_password(
    client, session_factory, monkeypatch, create_user
):
    user = create_user("jdoe", password="local-pass")
    _enable_ldap(session_factory, monkeypatch)

    assert _login(client, "jdoe", "ldap-pass").status_code == 200

    with session_factory() as session:
        refreshed = session.get(User, user.id)
        assert refreshed.hashed_password == ""
        assert refreshed.auth_source == "ldap"
    events = _events(session_factory, "user.local_password_removed")
    assert len(events) == 1
    assert events[0].details == {"source": "ldap"}
    assert events[0].target_id == str(user.id)

    # The old local password no longer gets in.
    assert _login(client, "jdoe", "local-pass").status_code == 401


def test_ldap_relogin_without_local_password_logs_nothing(
    client, session_factory, monkeypatch, create_user
):
    create_user("jdoe", password="local-pass")
    _enable_ldap(session_factory, monkeypatch)

    assert _login(client, "jdoe", "ldap-pass").status_code == 200
    assert _login(client, "jdoe", "ldap-pass").status_code == 200

    assert len(_events(session_factory, "user.local_password_removed")) == 1


def test_local_login_keeps_local_password(
    client, session_factory, monkeypatch, create_user
):
    create_user("jdoe", password="local-pass")
    _enable_ldap(session_factory, monkeypatch)

    assert _login(client, "jdoe", "local-pass").status_code == 200

    with session_factory() as session:
        assert (
            session.exec(select(User).where(User.name == "jdoe")).one().hashed_password
        )
    assert _events(session_factory, "user.local_password_removed") == []
