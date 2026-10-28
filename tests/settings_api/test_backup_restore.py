"""Tests for POST /api/v1/settings/backup/restore/.

Covers backups from before dictionaries existed: their free-text glossary
(or, older still, whisper_prompt) becomes a dictionary attached to the
category, so restoring one does not silently turn off term correction (see
AGENTS.md "Phonetic Term Correction"). Also the export/restore round trip of
global dictionaries.
"""

import io
import json
import re


def _attached_terms(client, headers, category):
    terms = []
    for dictionary_id in category["dictionary_ids"]:
        response = client.get(
            f"/api/v1/settings/dictionaries/{dictionary_id}", headers=headers
        )
        terms += response.json()["terms"]
    return terms


def test_restore_backfills_glossary_from_whisper_prompt_when_missing(
    client, create_user, auth_headers
):
    admin = create_user("admin_user", role="admin")
    headers = auth_headers(admin)

    # A backup produced before the glossary field existed — no "glossary" key.
    backup = {
        "settings": {
            "categories": [
                {
                    "name": "Kardiologie",
                    "description": "Herz",
                    "system_prompt": "Fasse zusammen.",
                    "whisper_prompt": "Sertralin, Ibuprofen",
                    "llm_override_enabled": False,
                    "llm_model": None,
                    "llm_api_endpoint": None,
                    "llm_api_key": None,
                    "llm_temperature": None,
                    "llm_max_tokens": None,
                    "llm_top_p": None,
                    "llm_frequency_penalty": None,
                    "llm_enable_thinking": None,
                    "user_id": None,
                }
            ],
        }
    }
    file_bytes = io.BytesIO(json.dumps(backup).encode())

    response = client.post(
        "/api/v1/settings/backup/restore/",
        files={"file": ("backup.json", file_bytes, "application/json")},
        headers=headers,
    )

    assert response.status_code == 200

    categories_response = client.get("/api/v1/settings/categories/", headers=headers)
    categories = categories_response.json()
    assert len(categories) == 1
    assert categories[0]["whisper_prompt"] == "Sertralin, Ibuprofen"
    assert _attached_terms(client, headers, categories[0]) == [
        "Sertralin",
        "Ibuprofen",
    ]


def test_restore_keeps_explicit_glossary_when_present(
    client, create_user, auth_headers
):
    admin = create_user("admin_user", role="admin")
    headers = auth_headers(admin)

    backup = {
        "settings": {
            "categories": [
                {
                    "name": "Kardiologie",
                    "description": "Herz",
                    "system_prompt": "Fasse zusammen.",
                    "whisper_prompt": "Stil-Hinweis",
                    "glossary": "Metformin",
                    "llm_override_enabled": False,
                    "llm_model": None,
                    "llm_api_endpoint": None,
                    "llm_api_key": None,
                    "llm_temperature": None,
                    "llm_max_tokens": None,
                    "llm_top_p": None,
                    "llm_frequency_penalty": None,
                    "llm_enable_thinking": None,
                    "user_id": None,
                }
            ],
        }
    }
    file_bytes = io.BytesIO(json.dumps(backup).encode())

    response = client.post(
        "/api/v1/settings/backup/restore/",
        files={"file": ("backup.json", file_bytes, "application/json")},
        headers=headers,
    )

    assert response.status_code == 200

    categories_response = client.get("/api/v1/settings/categories/", headers=headers)
    categories = categories_response.json()
    assert categories[0]["whisper_prompt"] == "Stil-Hinweis"
    assert _attached_terms(client, headers, categories[0]) == ["Metformin"]


def _restore(client, headers, backup):
    file_bytes = io.BytesIO(json.dumps(backup).encode())
    return client.post(
        "/api/v1/settings/backup/restore/",
        files={"file": ("backup.json", file_bytes, "application/json")},
        headers=headers,
    )


LEGACY_WHISPER = {
    "live_backend": "api",
    "live_api_endpoint": "http://old-whisper:9000",
    "live_api_model": "large-v3-turbo",
    "final_backend": "api",
    "final_api_endpoint": "http://whisper:9000",
    "language": "de",
    # Fields of the removed near-live Whisper path.
    "chunk_length_s": 3,
    "overlap_s": 0.0,
    "left_context_s": 1.0,
    "live_beam_size": 1,
    "final_beam_size": 5,
}


def test_restore_ignores_removed_whisper_fields_of_old_backups(
    client, create_user, auth_headers
):
    """Old backups still carry the near-live Whisper fields; they must not break."""
    admin = create_user("admin_user", role="admin")
    headers = auth_headers(admin)

    # Restoring twice covers both branches: insert (no row yet) and update.
    for _ in range(2):
        response = _restore(client, headers, {"settings": {"whisper": LEGACY_WHISPER}})
        assert response.status_code == 200, response.text

    stored = client.get("/api/v1/settings/whisper-settings/", headers=headers).json()
    assert stored["final_api_endpoint"] == "http://whisper:9000"
    assert stored["final_beam_size"] == 5
    for removed in ("chunk_length_s", "overlap_s", "left_context_s", "live_beam_size"):
        assert removed not in stored


def test_restore_turns_legacy_live_api_backend_into_disabled(
    client, create_user, auth_headers
):
    admin = create_user("admin_user", role="admin")
    headers = auth_headers(admin)

    assert (
        _restore(client, headers, {"settings": {"whisper": LEGACY_WHISPER}}).status_code
        == 200
    )

    stored = client.get("/api/v1/settings/whisper-settings/", headers=headers).json()
    assert stored["live_backend"] == "disabled"


def test_export_and_restore_round_trip_global_dictionaries(
    client, create_user, auth_headers
):
    admin = create_user("admin_user", role="admin")
    headers = auth_headers(admin)
    icd = client.post(
        "/api/v1/settings/dictionaries/",
        json={"name": "ICD", "scope": "global", "terms": ["Hypertonie, essentiell"]},
        headers=headers,
    ).json()["id"]
    client.post(
        "/api/v1/settings/categories/",
        json={
            "name": "Allgemein",
            "description": "d",
            "system_prompt": "s",
            "dictionary_ids": [icd],
        },
        headers=headers,
    )

    backup = client.get("/api/v1/settings/backup/", headers=headers).json()
    assert backup["settings"]["dictionaries"] == [
        {"name": "ICD", "terms": ["Hypertonie, essentiell"]}
    ]

    assert _restore(client, headers, backup).status_code == 200

    categories = client.get("/api/v1/settings/categories/", headers=headers).json()
    assert _attached_terms(client, headers, categories[0]) == ["Hypertonie, essentiell"]


SECRETS = {
    "whisper": {"live_api_key": "sk-parakeet", "final_api_key": "sk-whisper"},
    "llm": {"llm_api_key": "sk-llm", "sanitizer_api_key": "sk-entityguard"},
    "ldap": {
        "bind_user_password": "ldap-bind-pw",
        "cert_data": "-----BEGIN CERTIFICATE-----geheim",
        "cert_filename": "ca.pem",
    },
    "oidc": {"client_secret": "oidc-client-secret"},
}


def _seed_settings(session_factory):
    """Store one row per credential-bearing settings table plus a category."""
    from backend.components.models.categories import Categories
    from backend.components.models.client_settings_model import ClientSettingsModel
    from backend.components.models.ldap_model import LdapSettingsModel
    from backend.components.models.llm_settings_model import LlmSettingsModel
    from backend.components.models.oidc_model import OidcSettingsModel
    from backend.components.models.settings_model import WhisperSettingsModel

    with session_factory() as session:
        session.add(
            WhisperSettingsModel(
                live_backend="parakeet",
                live_api_endpoint="http://parakeet:5001/v1",
                **SECRETS["whisper"],
            )
        )
        session.add(LlmSettingsModel(**SECRETS["llm"]))
        session.add(
            LdapSettingsModel(
                server_host="dc.example.org",
                server_port=636,
                base_dn="dc=example,dc=org",
                user_dn="sAMAccountName",
                bind_user_dn="cn=svc,dc=example,dc=org",
                **SECRETS["ldap"],
            )
        )
        session.add(
            OidcSettingsModel(
                enabled=True,
                provider_url="https://idp.example.org/realms/opendox",
                client_id="opendox",
                **SECRETS["oidc"],
            )
        )
        session.add(ClientSettingsModel(clipboard_clear_after_seconds=45))
        session.add(
            Categories(
                name="Kardiologie",
                description="Herz",
                system_prompt="Fasse zusammen.",
                llm_override_enabled=True,
                llm_api_key="sk-category",
            )
        )
        session.commit()


def test_export_contains_all_global_settings_but_no_credentials(
    client, create_user, auth_headers, session_factory
):
    admin = create_user("admin_user", role="admin")
    headers = auth_headers(admin)
    _seed_settings(session_factory)

    response = client.get("/api/v1/settings/backup/", headers=headers)
    assert response.status_code == 200
    for values in SECRETS.values():
        for value in values.values():
            assert value not in response.text
    assert "sk-category" not in response.text

    settings = response.json()["settings"]
    for key in ("whisper", "llm", "ldap", "oidc", "audio", "session", "client"):
        assert key in settings
    assert settings["whisper"]["live_backend"] == "parakeet"
    assert settings["whisper"]["live_api_endpoint"] == "http://parakeet:5001/v1"
    assert settings["ldap"]["server_host"] == "dc.example.org"
    assert settings["oidc"]["client_id"] == "opendox"
    assert settings["client"]["clipboard_clear_after_seconds"] == 45
    for key, fields in SECRETS.items():
        for field in fields:
            assert field not in settings[key]
    assert "llm_api_key" not in settings["categories"][0]


def test_restore_applies_settings_and_keeps_stored_credentials(
    client, create_user, auth_headers, session_factory
):
    admin = create_user("admin_user", role="admin")
    headers = auth_headers(admin)
    _seed_settings(session_factory)

    backup = client.get("/api/v1/settings/backup/", headers=headers).json()
    backup["settings"]["whisper"]["live_api_endpoint"] = "http://parakeet-2:5001/v1"
    backup["settings"]["ldap"]["server_host"] = "dc2.example.org"
    backup["settings"]["oidc"]["client_id"] = "opendox-prod"
    backup["settings"]["client"]["clipboard_clear_after_seconds"] = 10
    assert _restore(client, headers, backup).status_code == 200

    whisper = client.get("/api/v1/settings/whisper-settings/", headers=headers).json()
    llm = client.get("/api/v1/settings/llm-settings/", headers=headers).json()
    ldap = client.get("/api/v1/settings/ldap-settings/", headers=headers).json()
    oidc = client.get("/api/v1/settings/oidc-settings/", headers=headers).json()
    assert whisper["live_api_endpoint"] == "http://parakeet-2:5001/v1"
    assert ldap["server_host"] == "dc2.example.org"
    assert oidc["client_id"] == "opendox-prod"
    stored = {"whisper": whisper, "llm": llm, "ldap": ldap, "oidc": oidc}
    for key, values in SECRETS.items():
        for field, value in values.items():
            assert stored[key][field] == value

    from sqlmodel import select

    from backend.components.models.categories import Categories
    from backend.components.models.client_settings_model import ClientSettingsModel

    with session_factory() as session:
        category = session.exec(select(Categories)).one()
        assert category.llm_api_key == "sk-category"
        client_row = session.exec(select(ClientSettingsModel)).one()
        assert client_row.clipboard_clear_after_seconds == 10


def test_restore_ignores_credentials_of_old_backups(
    client, create_user, auth_headers, session_factory
):
    """An old backup with plaintext keys must not put back a rotated key."""
    admin = create_user("admin_user", role="admin")
    headers = auth_headers(admin)
    _seed_settings(session_factory)

    old = {
        "settings": {
            "whisper": {"final_api_key": "sk-old", "live_api_key": "sk-old"},
            "llm": {"llm_api_key": "sk-old", "sanitizer_api_key": "sk-old"},
            "ldap": {
                "server_host": "dc.example.org",
                "server_port": 636,
                "base_dn": "dc=example,dc=org",
                "user_dn": "sAMAccountName",
                "bind_user_password": "old-pw",
                "cert_data": "old-cert",
                "cert_filename": "old.pem",
            },
        }
    }
    assert _restore(client, headers, old).status_code == 200

    whisper = client.get("/api/v1/settings/whisper-settings/", headers=headers).json()
    llm = client.get("/api/v1/settings/llm-settings/", headers=headers).json()
    ldap = client.get("/api/v1/settings/ldap-settings/", headers=headers).json()
    stored = {"whisper": whisper, "llm": llm, "ldap": ldap}
    for key in stored:
        for field, value in SECRETS[key].items():
            assert stored[key][field] == value


def test_backup_covers_every_settings_table_and_credential_field():
    """A new settings table or credential field must not slip past the backup."""
    from sqlmodel import SQLModel

    from backend.components.models.categories import Categories
    from backend.views.settings_api import settings_routes as routes

    covered = {model_cls.__tablename__ for model_cls, _ in routes._BACKUP_SINGLETONS}
    settings_tables = {
        name for name in SQLModel.metadata.tables if name.endswith("settingsmodel")
    }
    assert settings_tables == covered

    credential = re.compile(r"(_key|secret|password|_token|cert)(_|$)")
    models = [*routes._BACKUP_SINGLETONS, (Categories, "categories")]
    for model_cls, key in models:
        for field in model_cls.model_fields:
            if credential.search(field):
                assert field in routes._BACKUP_SECRET_FIELDS.get(key, ()), (
                    f"{key}.{field} looks like a credential but is backed up"
                )
