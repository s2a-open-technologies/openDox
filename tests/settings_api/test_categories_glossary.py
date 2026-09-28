"""Tests for the categories.glossary field (term-correction source, decoupled
from whisper_prompt — see AGENTS.md "Phonetic Term Correction").
"""


def test_create_category_persists_glossary(client, create_user, auth_headers):
    admin = create_user("admin_user", role="admin")

    response = client.post(
        "/api/v1/settings/categories/",
        json={
            "name": "Kardiologie",
            "description": "Herz",
            "system_prompt": "Fasse zusammen.",
            "whisper_prompt": "kurzer Stil-Hinweis",
            "glossary": "Sertralin, Ibuprofen, Metformin",
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["glossary"] == "Sertralin, Ibuprofen, Metformin"
    assert body["whisper_prompt"] == "kurzer Stil-Hinweis"


def test_update_category_can_change_glossary_independently_of_whisper_prompt(
    client, create_user, auth_headers
):
    admin = create_user("admin_user", role="admin")
    headers = auth_headers(admin)

    create_response = client.post(
        "/api/v1/settings/categories/",
        json={
            "name": "Kardiologie",
            "description": "Herz",
            "system_prompt": "Fasse zusammen.",
            "whisper_prompt": "Stil-Hinweis",
            "glossary": "Sertralin",
        },
        headers=headers,
    )
    category_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/v1/settings/categories/{category_id}",
        json={
            "name": "Kardiologie",
            "description": "Herz",
            "system_prompt": "Fasse zusammen.",
            "whisper_prompt": "Stil-Hinweis",
            "glossary": "Sertralin, Ibuprofen",
        },
        headers=headers,
    )

    assert update_response.status_code == 200
    body = update_response.json()
    assert body["glossary"] == "Sertralin, Ibuprofen"
    assert body["whisper_prompt"] == "Stil-Hinweis"
