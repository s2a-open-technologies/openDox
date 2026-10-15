"""Tests for POST /api/v1/settings/backup/restore/.

Covers the glossary backfill for backups made before the
glossary/whisper_prompt split — restoring an older backup must not
silently turn off term correction (see AGENTS.md "Phonetic Term
Correction").
"""

import io
import json


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
    assert categories[0]["glossary"] == "Sertralin, Ibuprofen"


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
    assert categories[0]["glossary"] == "Metformin"


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
