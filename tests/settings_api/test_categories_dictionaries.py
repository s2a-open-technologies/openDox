"""Tests for attaching dictionaries to categories (``dictionary_ids``).

A global category takes global dictionaries only; a personal category takes
global ones plus its owner's. The term-correction glossary is the category's
dictionaries plus every personal dictionary of the recording's owner (see
dictionary_service.glossary_for_category).
"""

from backend.components.models.categories import Categories
from backend.components.services.dictionary_service import glossary_for_category

CATEGORIES = "/api/v1/settings/categories/"
DICTIONARIES = "/api/v1/settings/dictionaries/"


def _dictionary(client, headers, name, scope, terms):
    response = client.post(
        DICTIONARIES,
        json={"name": name, "scope": scope, "terms": terms},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _category_payload(**overrides):
    return {
        "name": "Kardiologie",
        "description": "Herz",
        "system_prompt": "Fasse zusammen.",
        **overrides,
    }


def test_global_category_with_global_dictionary(client, create_user, auth_headers):
    admin = create_user("admin_user", role="admin")
    headers = auth_headers(admin)
    icd = _dictionary(client, headers, "ICD", "global", ["Hypertonie"])

    created = client.post(
        CATEGORIES, json=_category_payload(dictionary_ids=[icd]), headers=headers
    )

    assert created.status_code == 200, created.text
    assert created.json()["dictionary_ids"] == [icd]
    listing = client.get(CATEGORIES, headers=headers).json()
    assert listing[0]["dictionary_ids"] == [icd]


def test_global_category_rejects_personal_dictionary(client, create_user, auth_headers):
    admin = create_user("admin_user", role="admin")
    headers = auth_headers(admin)
    own = _dictionary(client, headers, "Privat", "personal", ["x"])

    response = client.post(
        CATEGORIES, json=_category_payload(dictionary_ids=[own]), headers=headers
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "dictionary_scope_mismatch"


def test_personal_category_takes_global_and_own_dictionaries(
    client, create_user, auth_headers
):
    mod = create_user("mod", role="moderator")
    alice = create_user("alice")
    icd = _dictionary(client, auth_headers(mod), "ICD", "global", ["Hypertonie"])
    own = _dictionary(client, auth_headers(alice), "Test", "personal", ["Sertralin"])

    response = client.post(
        CATEGORIES,
        json=_category_payload(name="Meine", dictionary_ids=[icd, own]),
        headers=auth_headers(alice),
    )

    assert response.status_code == 200, response.text
    assert sorted(response.json()["dictionary_ids"]) == sorted([icd, own])


def test_personal_category_rejects_foreign_personal_dictionary(
    client, create_user, auth_headers
):
    alice = create_user("alice")
    bob = create_user("bob")
    bobs = _dictionary(client, auth_headers(bob), "Bob", "personal", ["x"])

    response = client.post(
        CATEGORIES,
        json=_category_payload(name="Meine", dictionary_ids=[bobs]),
        headers=auth_headers(alice),
    )

    assert response.status_code == 400


def test_unknown_dictionary_is_404(client, create_user, auth_headers):
    admin = create_user("admin_user", role="admin")

    response = client.post(
        CATEGORIES,
        json=_category_payload(dictionary_ids=[999]),
        headers=auth_headers(admin),
    )

    assert response.status_code == 404


def test_update_without_dictionary_ids_keeps_links(client, create_user, auth_headers):
    admin = create_user("admin_user", role="admin")
    headers = auth_headers(admin)
    icd = _dictionary(client, headers, "ICD", "global", ["Hypertonie"])
    category_id = client.post(
        CATEGORIES, json=_category_payload(dictionary_ids=[icd]), headers=headers
    ).json()["id"]

    kept = client.put(
        f"{CATEGORIES}{category_id}",
        json=_category_payload(description="neu"),
        headers=headers,
    )
    cleared = client.put(
        f"{CATEGORIES}{category_id}",
        json=_category_payload(dictionary_ids=[]),
        headers=headers,
    )

    assert kept.json()["dictionary_ids"] == [icd]
    assert cleared.json()["dictionary_ids"] == []


def test_glossary_for_category_merges_and_dedupes(
    client, create_user, auth_headers, session_factory
):
    admin = create_user("admin_user", role="admin")
    headers = auth_headers(admin)
    first = _dictionary(client, headers, "A", "global", ["Sertralin", "Metformin"])
    second = _dictionary(client, headers, "B", "global", ["metformin", "Ibuprofen"])
    category_id = client.post(
        CATEGORIES,
        json=_category_payload(
            whisper_prompt="nie im Glossar", dictionary_ids=[first, second]
        ),
        headers=headers,
    ).json()["id"]

    with session_factory() as session:
        category = session.get(Categories, category_id)
        glossary = glossary_for_category(session, category)

    assert glossary == ["Sertralin", "Metformin", "Ibuprofen"]


def test_glossary_for_category_without_category_is_empty(session_factory):
    with session_factory() as session:
        assert glossary_for_category(session, None) == []


def test_glossary_includes_owners_personal_dictionaries_without_link(
    client, create_user, auth_headers, session_factory
):
    admin = create_user("admin_user", role="admin")
    owner = create_user("owner", role="user")
    other = create_user("other", role="user")
    admin_headers = auth_headers(admin)
    icd = _dictionary(client, admin_headers, "ICD", "global", ["Hypertonie"])
    _dictionary(
        client, auth_headers(owner), "Mein", "personal", ["hypertonie", "Dr. Ölz"]
    )
    _dictionary(client, auth_headers(other), "Fremd", "personal", ["Geheim"])
    category_id = client.post(
        CATEGORIES, json=_category_payload(dictionary_ids=[icd]), headers=admin_headers
    ).json()["id"]

    with session_factory() as session:
        category = session.get(Categories, category_id)
        with_owner = glossary_for_category(session, category, owner.id)
        without_category = glossary_for_category(session, None, owner.id)
        without_owner = glossary_for_category(session, category)

    assert with_owner == ["Hypertonie", "Dr. Ölz"]
    assert without_category == ["hypertonie", "Dr. Ölz"]
    assert without_owner == ["Hypertonie"]


def test_admin_creates_personal_category_with_scope(client, create_user, auth_headers):
    admin = create_user("admin_user", role="admin")
    headers = auth_headers(admin)

    personal = client.post(
        CATEGORIES,
        json=_category_payload(
            scope="personal", llm_override_enabled=True, llm_model="x"
        ),
        headers=headers,
    )
    global_ = client.post(CATEGORIES, json=_category_payload(), headers=headers)

    assert personal.status_code == 200, personal.text
    assert personal.json()["user_id"] == admin.id
    assert personal.json()["llm_override_enabled"] is False
    assert global_.json()["user_id"] is None


def test_user_cannot_create_global_category_via_scope(
    client, create_user, auth_headers
):
    user = create_user("plain", role="user")

    response = client.post(
        CATEGORIES, json=_category_payload(scope="global"), headers=auth_headers(user)
    )

    assert response.json()["user_id"] == user.id
