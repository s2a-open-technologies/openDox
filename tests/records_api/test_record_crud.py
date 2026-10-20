"""Route-level tests for the plain CRUD endpoints in record_api/record.py.

Only covers routes with zero ASR/LLM/session_store/background-task
involvement (GET/PUT/DELETE by id, list-records) — the recording pipeline
itself is out of scope for this suite.
"""

from backend.components.models.categories import Categories
from backend.components.models.record_model import Record


def _create_record(session_factory, **overrides) -> Record:
    defaults = dict(
        session_id="session-1",
        user_id=1,
        category_id=None,
        title="Test Record",
        content="patient note",
        timestamp="01.01.2026 00:00:00",
        summarize="summary",
        file="",
        archived=False,
        task_id=None,
    )
    defaults.update(overrides)
    with session_factory() as session:
        record = Record(**defaults)
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def test_get_record_as_owner_returns_plaintext(
    client, create_user, auth_headers, session_factory
):
    owner = create_user("dr.mueller")
    record = _create_record(session_factory, user_id=owner.id)
    url = f"/api/v1/records/record/{record.id}"

    response = client.get(url, headers=auth_headers(owner))

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "patient note"
    assert body["summarize"] == "summary"


def test_get_record_as_non_owner_is_forbidden(
    client, create_user, auth_headers, session_factory
):
    owner = create_user("dr.mueller")
    other = create_user("dr.schmidt")
    record = _create_record(session_factory, user_id=owner.id)
    url = f"/api/v1/records/record/{record.id}"

    response = client.get(url, headers=auth_headers(other))

    assert response.status_code == 403


def test_admin_cannot_access_another_users_record(
    client, create_user, auth_headers, session_factory
):
    # Recordings are private to their owner; the admin role gets no bypass.
    owner = create_user("dr.mueller")
    admin = create_user("admin1", role="admin")
    record = _create_record(session_factory, user_id=owner.id)
    headers = auth_headers(admin)
    base = f"/api/v1/records/record/{record.id}"

    assert client.get(base, headers=headers).status_code == 403
    assert client.get(f"{base}/audio", headers=headers).status_code == 403
    assert client.put(base, json={"title": "x"}, headers=headers).status_code == 403
    assert client.delete(base, headers=headers).status_code == 403
    assert (
        client.get(
            f"/api/v1/records/list-records/{owner.id}", headers=headers
        ).status_code
        == 403
    )


def test_get_nonexistent_record_returns_404(client, create_user, auth_headers):
    user = create_user("dr.mueller")

    response = client.get("/api/v1/records/record/999", headers=auth_headers(user))

    assert response.status_code == 404


def test_update_record_persists_new_content(
    client, create_user, auth_headers, session_factory
):
    owner = create_user("dr.mueller")
    record = _create_record(session_factory, user_id=owner.id)
    url = f"/api/v1/records/record/{record.id}"

    response = client.put(
        url,
        headers=auth_headers(owner),
        json={
            "content": "updated note",
            "summarize": "updated summary",
            "title": "New title",
        },
    )
    assert response.status_code == 200

    follow_up = client.get(url, headers=auth_headers(owner))
    body = follow_up.json()
    assert body["content"] == "updated note"
    assert body["summarize"] == "updated summary"
    assert body["title"] == "New title"


def test_update_record_changes_category(
    client, create_user, auth_headers, session_factory
):
    owner = create_user("dr.mueller")
    record = _create_record(session_factory, user_id=owner.id)
    with session_factory() as session:
        category = Categories(
            name="Kardiologie", description="", system_prompt="prompt"
        )
        session.add(category)
        session.commit()
        session.refresh(category)
        category_id = category.id
    url = f"/api/v1/records/record/{record.id}"

    response = client.put(
        url, headers=auth_headers(owner), json={"category_id": category_id}
    )

    assert response.status_code == 200
    assert response.json()["category_id"] == category_id


def test_update_record_with_unknown_category_returns_404(
    client, create_user, auth_headers, session_factory
):
    owner = create_user("dr.mueller")
    record = _create_record(session_factory, user_id=owner.id)
    url = f"/api/v1/records/record/{record.id}"

    response = client.put(url, headers=auth_headers(owner), json={"category_id": 999})

    assert response.status_code == 404


def test_delete_record_as_owner_removes_it(
    client, create_user, auth_headers, session_factory
):
    owner = create_user("dr.mueller")
    record = _create_record(session_factory, user_id=owner.id)
    url = f"/api/v1/records/record/{record.id}"

    response = client.delete(url, headers=auth_headers(owner))
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    follow_up = client.get(url, headers=auth_headers(owner))
    assert follow_up.status_code == 404


def test_delete_nonexistent_record_returns_200_with_error_body(
    client, create_user, auth_headers
):
    """Documents existing behavior: missing-record delete is a 200, not a 404."""
    user = create_user("dr.mueller")

    response = client.delete("/api/v1/records/record/999", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json() == {"error": "Record not found"}


def test_list_records_filters_by_archived_and_orders_desc(
    client, create_user, auth_headers, session_factory
):
    owner = create_user("dr.mueller")
    other = create_user("dr.schmidt")
    first = _create_record(
        session_factory, user_id=owner.id, session_id="s1", archived=False
    )
    second = _create_record(
        session_factory, user_id=owner.id, session_id="s2", archived=False
    )
    _create_record(session_factory, user_id=owner.id, session_id="s3", archived=True)
    _create_record(session_factory, user_id=other.id, session_id="s4", archived=False)

    active = client.get(
        f"/api/v1/records/list-records/{owner.id}", headers=auth_headers(owner)
    )
    assert active.status_code == 200
    active_ids = [r["id"] for r in active.json()]
    assert active_ids == [second.id, first.id]

    archived = client.get(
        f"/api/v1/records/list-records/{owner.id}",
        params={"archived": "true"},
        headers=auth_headers(owner),
    )
    assert archived.status_code == 200
    assert len(archived.json()) == 1


def test_list_records_as_non_owner_is_forbidden(client, create_user, auth_headers):
    owner = create_user("dr.mueller")
    other = create_user("dr.schmidt")

    response = client.get(
        f"/api/v1/records/list-records/{owner.id}", headers=auth_headers(other)
    )

    assert response.status_code == 403
