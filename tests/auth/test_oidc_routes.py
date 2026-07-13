"""Route-level tests for backend.views.auth_api.oidc_routes.

External provider calls are avoided entirely by monkeypatching the
OidcService methods the routes call — this suite only exercises openDox's
own routing/state/provisioning logic, not real network interaction (that's
covered separately by tests/services/test_oidc_service.py).
"""

from backend.components.models.oidc_model import OidcSettingsModel
from backend.components.services.oidc import OidcDiscoveryError, OidcService
from backend.views.auth_api.oidc_routes import _serializer


def _create_settings(session_factory, **overrides) -> OidcSettingsModel:
    defaults = dict(
        enabled=True,
        provider_url="https://provider.example.com",
        client_id="my-client",
        client_secret="my-secret",
        scopes="openid email profile",
        group_claim="groups",
        admin_groups="admins",
        moderator_groups="mods",
        username_claim="preferred_username",
    )
    defaults.update(overrides)
    with session_factory() as session:
        settings = OidcSettingsModel(**defaults)
        session.add(settings)
        session.commit()
        session.refresh(settings)
        return settings


def test_status_reports_disabled_when_unconfigured(client):
    response = client.get("/api/v1/auth/oidc/status")

    assert response.status_code == 200
    assert response.json() == {"enabled": False}


def test_status_reports_enabled_when_configured(client, session_factory):
    _create_settings(session_factory, enabled=True)

    response = client.get("/api/v1/auth/oidc/status")

    assert response.json() == {"enabled": True}


def test_login_returns_503_when_not_configured(client):
    response = client.get("/api/v1/auth/oidc/login", follow_redirects=False)

    assert response.status_code == 503


def test_login_redirects_and_sets_signed_state_cookie(
    client, session_factory, monkeypatch
):
    _create_settings(session_factory)
    monkeypatch.setattr(
        OidcService,
        "authorization_url",
        lambda self, redirect_uri, state: (
            f"https://provider.example.com/auth?state={state}"
        ),
    )

    response = client.get("/api/v1/auth/oidc/login", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith(
        "https://provider.example.com/auth?state="
    )
    assert "oidc_state" in response.cookies


def test_login_returns_502_on_discovery_failure(client, session_factory, monkeypatch):
    _create_settings(session_factory)

    def raise_discovery_error(self, redirect_uri, state):
        raise OidcDiscoveryError("provider unreachable")

    monkeypatch.setattr(OidcService, "authorization_url", raise_discovery_error)

    response = client.get("/api/v1/auth/oidc/login", follow_redirects=False)

    assert response.status_code == 502


def test_callback_rejects_missing_state(client, session_factory):
    _create_settings(session_factory)

    response = client.get(
        "/api/v1/auth/oidc/callback", params={"code": "abc"}, follow_redirects=False
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "State fehlt"


def test_callback_rejects_state_mismatch(client, session_factory):
    _create_settings(session_factory)
    signed_state = _serializer.dumps({"state": "expected-state"})
    client.cookies.set("oidc_state", signed_state)

    response = client.get(
        "/api/v1/auth/oidc/callback",
        params={"code": "abc", "state": "different-state"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "State mismatch"


def test_callback_rejects_missing_code(client, session_factory):
    _create_settings(session_factory)
    signed_state = _serializer.dumps({"state": "expected-state"})
    client.cookies.set("oidc_state", signed_state)

    response = client.get(
        "/api/v1/auth/oidc/callback",
        params={"state": "expected-state"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Code fehlt"


def test_callback_requires_id_token_in_response(client, session_factory, monkeypatch):
    _create_settings(session_factory)
    signed_state = _serializer.dumps({"state": "expected-state"})
    client.cookies.set("oidc_state", signed_state)
    monkeypatch.setattr(
        OidcService,
        "exchange_code",
        lambda self, code, redirect_uri: {"access_token": "at"},
    )

    response = client.get(
        "/api/v1/auth/oidc/callback",
        params={"code": "abc", "state": "expected-state"},
        follow_redirects=False,
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Kein id_token erhalten"


def _patch_happy_path(monkeypatch, *, role="user", username="jdoe"):
    monkeypatch.setattr(
        OidcService,
        "exchange_code",
        lambda self, code, redirect_uri: {"access_token": "at", "id_token": "it"},
    )
    monkeypatch.setattr(
        OidcService, "verify_id_token", lambda self, id_token: {"sub": "provider-sub"}
    )
    monkeypatch.setattr(OidcService, "get_userinfo", lambda self, access_token: {})
    monkeypatch.setattr(OidcService, "resolve_username", lambda self, claims: username)
    monkeypatch.setattr(OidcService, "map_groups_to_role", lambda self, claims: role)


def test_callback_provisions_new_user_and_redirects_with_tokens(
    client, session_factory, monkeypatch
):
    _create_settings(session_factory)
    signed_state = _serializer.dumps({"state": "expected-state"})
    client.cookies.set("oidc_state", signed_state)
    _patch_happy_path(monkeypatch, role="admin", username="new.sso.user")

    response = client.get(
        "/api/v1/auth/oidc/callback",
        params={"code": "abc", "state": "expected-state"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("/login?access_token=")
    assert "refresh_token=" in location
    assert response.cookies.get("oidc_state") in (None, "")

    with session_factory() as session:
        from sqlmodel import select

        from backend.components.models.user_model import User

        user = session.exec(select(User).where(User.name == "new.sso.user")).one()
        assert user.role == "admin"
        assert user.is_active is True


def test_callback_updates_existing_user_role_on_relogin(
    client, session_factory, monkeypatch, create_user
):
    _create_settings(session_factory)
    existing = create_user("dr.mueller", role="user")
    signed_state = _serializer.dumps({"state": "expected-state"})
    client.cookies.set("oidc_state", signed_state)
    _patch_happy_path(monkeypatch, role="moderator", username="dr.mueller")

    response = client.get(
        "/api/v1/auth/oidc/callback",
        params={"code": "abc", "state": "expected-state"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with session_factory() as session:
        from backend.components.models.user_model import User

        refreshed = session.get(User, existing.id)
        assert refreshed.role == "moderator"
