"""Tests for the admin-only /users CRUD routes in auth_routes.py."""


def test_list_users_as_regular_user_is_forbidden(client, create_user, auth_headers):
    user = create_user("dr.mueller", role="user")

    response = client.get("/api/v1/auth/users", headers=auth_headers(user))

    assert response.status_code == 403


def test_list_users_as_admin_returns_users(client, create_user, auth_headers):
    admin = create_user("admin1", role="admin")
    create_user("dr.mueller", role="user")

    response = client.get("/api/v1/auth/users", headers=auth_headers(admin))

    assert response.status_code == 200
    names = {u["name"] for u in response.json()}
    assert {"admin1", "dr.mueller"} <= names


def test_create_user_as_admin_persists_new_user(client, create_user, auth_headers):
    admin = create_user("admin1", role="admin")

    response = client.post(
        "/api/v1/auth/users",
        headers=auth_headers(admin),
        json={"name": "new.user", "password": "s3cret!", "role": "moderator"},
    )

    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "new.user"
    assert created["role"] == "moderator"

    follow_up = client.get(
        f"/api/v1/auth/users/{created['id']}", headers=auth_headers(admin)
    )
    assert follow_up.status_code == 200


def test_create_user_with_duplicate_name_returns_422(client, create_user, auth_headers):
    admin = create_user("admin1", role="admin")
    create_user("dr.mueller", role="user")

    response = client.post(
        "/api/v1/auth/users",
        headers=auth_headers(admin),
        json={"name": "dr.mueller", "password": "whatever", "role": "user"},
    )

    assert response.status_code == 422


def test_admin_cannot_delete_self(client, create_user, auth_headers):
    admin = create_user("admin1", role="admin")

    response = client.delete(
        f"/api/v1/auth/users/{admin.id}", headers=auth_headers(admin)
    )

    assert response.status_code == 400


def test_admin_can_delete_other_user(client, create_user, auth_headers):
    admin = create_user("admin1", role="admin")
    other = create_user("dr.mueller", role="user")

    response = client.delete(
        f"/api/v1/auth/users/{other.id}", headers=auth_headers(admin)
    )
    assert response.status_code == 200

    follow_up = client.get(
        f"/api/v1/auth/users/{other.id}", headers=auth_headers(admin)
    )
    assert follow_up.status_code == 404


def test_regular_user_cannot_update_own_profile(client, create_user, auth_headers):
    user = create_user("dr.mueller", role="user")

    response = client.put(
        f"/api/v1/auth/users/{user.id}",
        headers=auth_headers(user),
        json={"name": "new.name"},
    )

    assert response.status_code == 403


def test_admin_cannot_set_password_of_external_account(
    client, session_factory, create_user, auth_headers
):
    from backend.components.models.user_model import User

    admin = create_user("admin1", role="admin")
    target = create_user("dr.ldap", role="user")
    with session_factory() as session:
        row = session.get(User, target.id)
        row.auth_source = "ldap"
        row.hashed_password = ""
        session.add(row)
        session.commit()

    response = client.put(
        f"/api/v1/auth/users/{target.id}",
        json={"password": "new-local-pass"},
        headers=auth_headers(admin),
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "password_managed_externally"
    with session_factory() as session:
        assert session.get(User, target.id).hashed_password == ""


def test_admin_may_still_edit_other_fields_of_external_account(
    client, session_factory, create_user, auth_headers
):
    from backend.components.models.user_model import User

    admin = create_user("admin1", role="admin")
    target = create_user("dr.ldap", role="user")
    with session_factory() as session:
        row = session.get(User, target.id)
        row.auth_source = "oidc"
        session.add(row)
        session.commit()

    response = client.put(
        f"/api/v1/auth/users/{target.id}",
        json={"is_active": False},
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json()["auth_source"] == "oidc"


def test_admin_cannot_change_role_of_external_account(
    client, session_factory, create_user, auth_headers
):
    from backend.components.models.user_model import User

    admin = create_user("admin1", role="admin")
    target = create_user("dr.ldap", role="user")
    with session_factory() as session:
        row = session.get(User, target.id)
        row.auth_source = "ldap"
        session.add(row)
        session.commit()

    response = client.put(
        f"/api/v1/auth/users/{target.id}",
        json={"role": "admin"},
        headers=auth_headers(admin),
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "role_managed_externally"

    # Sending the unchanged role (as an old UI would) is fine.
    response = client.put(
        f"/api/v1/auth/users/{target.id}",
        json={"role": "user", "is_active": True},
        headers=auth_headers(admin),
    )
    assert response.status_code == 200
    with session_factory() as session:
        assert session.get(User, target.id).role == "user"
