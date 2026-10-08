"""The public self-registration endpoint was removed; accounts are admin-made."""


def test_register_endpoint_does_not_exist(client):
    resp = client.post(
        "/api/v1/auth/register", json={"name": "mallory", "password": "pw123456"}
    )
    assert resp.status_code in (404, 405)
