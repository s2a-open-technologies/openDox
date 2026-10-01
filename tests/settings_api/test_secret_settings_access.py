"""Settings GETs that carry secrets must not be readable without admin rights."""

import pytest
from sqlmodel import select

from backend.components.models.ldap_model import LdapSettingsModel
from backend.components.models.llm_settings_model import LlmSettingsModel
from backend.components.models.oidc_model import OidcSettingsModel
from backend.components.models.settings_model import WhisperSettingsModel

SECRET = "super-secret-value"

# endpoint, model, secret field
SECRET_ENDPOINTS = [
    ("/api/v1/settings/llm-settings/", LlmSettingsModel, "llm_api_key"),
    ("/api/v1/settings/llm-settings/", LlmSettingsModel, "sanitizer_api_key"),
    ("/api/v1/settings/ldap-settings/", LdapSettingsModel, "bind_user_password"),
    ("/api/v1/settings/oidc-settings/", OidcSettingsModel, "client_secret"),
]


def _store_secret(session_factory, model, field, **required):
    with session_factory() as session:
        row = session.exec(select(model)).first() or model(**required)
        setattr(row, field, SECRET)
        session.add(row)
        session.commit()


REQUIRED = {
    LdapSettingsModel: {
        "server_host": "ldap.example",
        "server_port": 389,
        "base_dn": "dc=example",
        "user_dn": "ou=people",
    },
}


@pytest.mark.parametrize("url,model,field", SECRET_ENDPOINTS)
def test_secret_settings_require_login(client, session_factory, url, model, field):
    _store_secret(session_factory, model, field, **REQUIRED.get(model, {}))

    response = client.get(url)

    assert response.status_code in (401, 403)
    assert SECRET not in response.text


@pytest.mark.parametrize("url,model,field", SECRET_ENDPOINTS)
def test_secret_settings_forbidden_for_normal_user(
    client, session_factory, create_user, auth_headers, url, model, field
):
    _store_secret(session_factory, model, field, **REQUIRED.get(model, {}))
    user = create_user("alice")

    response = client.get(url, headers=auth_headers(user))

    assert response.status_code == 403
    assert SECRET not in response.text


@pytest.mark.parametrize("url,model,field", SECRET_ENDPOINTS)
def test_secret_settings_visible_for_admin(
    client, session_factory, create_user, auth_headers, url, model, field
):
    _store_secret(session_factory, model, field, **REQUIRED.get(model, {}))
    admin = create_user("admin", role="admin")

    response = client.get(url, headers=auth_headers(admin))

    assert response.status_code == 200
    assert response.json()[field] == SECRET


@pytest.mark.parametrize("url,model,field", SECRET_ENDPOINTS)
def test_secret_settings_redacted_for_demo_viewer(
    client, session_factory, create_user, auth_headers, url, model, field
):
    _store_secret(session_factory, model, field, **REQUIRED.get(model, {}))
    viewer = create_user("demo", role="demo_viewer")

    response = client.get(url, headers=auth_headers(viewer))

    assert response.status_code == 200
    assert SECRET not in response.text
    assert not response.json()[field]


@pytest.mark.parametrize("field", ["live_api_key", "final_api_key"])
def test_whisper_settings_public_but_keys_redacted(client, session_factory, field):
    _store_secret(session_factory, WhisperSettingsModel, field)

    response = client.get("/api/v1/settings/whisper-settings/")

    assert response.status_code == 200
    assert response.json()["live_backend"]
    assert SECRET not in response.text
    assert not response.json()[field]


def test_whisper_settings_keys_redacted_for_normal_user(
    client, session_factory, create_user, auth_headers
):
    _store_secret(session_factory, WhisperSettingsModel, "final_api_key")
    user = create_user("alice")

    response = client.get(
        "/api/v1/settings/whisper-settings/", headers=auth_headers(user)
    )

    assert response.status_code == 200
    assert SECRET not in response.text


def test_whisper_settings_keys_visible_for_admin(
    client, session_factory, create_user, auth_headers
):
    _store_secret(session_factory, WhisperSettingsModel, "final_api_key")
    admin = create_user("admin", role="admin")

    response = client.get(
        "/api/v1/settings/whisper-settings/", headers=auth_headers(admin)
    )

    assert response.json()["final_api_key"] == SECRET


def test_whisper_settings_invalid_token_is_treated_as_anonymous(
    client, session_factory
):
    _store_secret(session_factory, WhisperSettingsModel, "final_api_key")

    response = client.get(
        "/api/v1/settings/whisper-settings/",
        headers={"Authorization": "Bearer not-a-token"},
    )

    assert response.status_code == 200
    assert SECRET not in response.text
