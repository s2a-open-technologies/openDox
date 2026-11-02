"""POST /api/v1/settings/ldap-settings/test never echoes exception text.

CodeQL py/stack-trace-exposure: ldap3 errors carry hosts, ports and library
details. The probe logs them and answers with a fixed error code instead.
"""

from ldap3.core.exceptions import LDAPSocketOpenError

import backend.views.settings_api.settings_routes as settings_routes

URL = "/api/v1/settings/ldap-settings/test"
PAYLOAD = {
    "server_host": "ldap.klinik.example",
    "server_port": 636,
    "base_dn": "dc=klinik,dc=example",
    "user_dn": "sAMAccountName",
}


def _failing_connect(exc):
    def connect(self):
        raise exc

    return connect


def test_unreachable_server_maps_to_code_without_details(
    client, create_user, auth_headers, monkeypatch
):
    admin = create_user("admin1", role="admin")
    monkeypatch.setattr(
        settings_routes.LdapService,
        "connect",
        _failing_connect(LDAPSocketOpenError("socket 10.1.2.3:636 refused")),
    )

    response = client.post(URL, json=PAYLOAD, headers=auth_headers(admin))

    body = response.json()
    assert body["success"] is False
    assert body["code"] == "ldap_unreachable"
    assert "10.1.2.3" not in response.text


def test_unknown_error_maps_to_generic_code(
    client, create_user, auth_headers, monkeypatch
):
    admin = create_user("admin1", role="admin")
    monkeypatch.setattr(
        settings_routes.LdapService,
        "connect",
        _failing_connect(RuntimeError("/etc/secret/path broke")),
    )

    response = client.post(URL, json=PAYLOAD, headers=auth_headers(admin))

    assert response.json()["code"] == "ldap_test_failed"
    assert "/etc/secret" not in response.text
