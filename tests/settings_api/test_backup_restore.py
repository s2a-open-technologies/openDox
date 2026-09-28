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
