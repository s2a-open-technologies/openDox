"""Tests for backend.components.services.ldap.LdapService.

Mocks ldap3.Connection so no real LDAP server is needed. ldap3.Server does
not open a socket at construction time, so only Connection needs patching.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.components.services import ldap as ldap_module
from backend.components.services.ldap import LdapService


def _settings(**overrides):
    defaults = dict(
        server_host="ldap.example.com",
        server_port=389,
        use_ssl=False,
        base_dn="dc=example,dc=com",
        user_dn="uid",
        search_filter=None,
        bind_user_dn="cn=admin,dc=example,dc=com",
        bind_user_password="admin-pass",
        cert_filename=None,
        cert_data=None,
        nested_groups=False,
        allowed_groups=None,
        admin_groups=None,
        moderator_groups=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _bind_connection(entries):
    """Fake service-account connection returned by the first Connection() call."""
    conn = MagicMock()
    conn.server = "fake-server"

    def fake_search(base_dn, search_filter, attributes=None, **kwargs):
        conn.entries = entries
        conn.last_search_filter = search_filter
        conn.last_base_dn = base_dn

    conn.search.side_effect = fake_search
    conn.entries = []
    return conn


def _user_entry(dn, member_of=None):
    entry = SimpleNamespace(entry_dn=dn)
    if member_of is not None:
        entry.memberOf = SimpleNamespace(values=member_of)
    return entry


@pytest.fixture
def patched_connection(monkeypatch):
    """Returns a helper to queue up Connection() return values / side effects."""

    def install(*connections):
        mock_connection = MagicMock(side_effect=list(connections))
        monkeypatch.setattr(ldap_module, "Connection", mock_connection)
        return mock_connection

    return install


def test_authenticate_succeeds_with_valid_credentials(patched_connection):
    bind_conn = _bind_connection(
        [
            _user_entry(
                "uid=jdoe,dc=example,dc=com",
                member_of=["cn=opendox-user,dc=example,dc=com"],
            )
        ]
    )
    user_conn = MagicMock()
    user_conn.bound = True
    patched_connection(bind_conn, user_conn)

    result = LdapService(_settings(allowed_groups="opendox-user")).authenticate(
        "jdoe", "secret"
    )

    assert result == {
        "success": True,
        "message": "Authentication successful",
        "role": "user",
    }
    bind_conn.unbind.assert_called_once()
    user_conn.unbind.assert_called_once()


def test_authenticate_fails_when_user_not_found(patched_connection):
    bind_conn = _bind_connection([])
    patched_connection(bind_conn)

    result = LdapService(_settings()).authenticate("ghost", "whatever")

    assert result == {"success": False, "message": "User not found"}


def test_authenticate_fails_with_invalid_credentials(patched_connection):
    bind_conn = _bind_connection([_user_entry("uid=jdoe,dc=example,dc=com")])
    user_conn = MagicMock()
    user_conn.bound = False
    patched_connection(bind_conn, user_conn)

    result = LdapService(_settings()).authenticate("jdoe", "wrong-password")

    assert result == {"success": False, "message": "Invalid credentials"}


def test_authenticate_catches_connection_exceptions(monkeypatch):
    monkeypatch.setattr(
        ldap_module, "Connection", MagicMock(side_effect=RuntimeError("conn refused"))
    )

    result = LdapService(_settings()).authenticate("jdoe", "secret")

    assert result == {"success": False, "message": "conn refused"}


def test_authenticate_uses_plain_filter_without_extra_search_filter(
    patched_connection,
):
    bind_conn = _bind_connection([_user_entry("uid=jdoe,dc=example,dc=com")])
    user_conn = MagicMock(bound=True)
    patched_connection(bind_conn, user_conn)

    LdapService(_settings(search_filter=None)).authenticate("jdoe", "secret")

    assert bind_conn.last_search_filter == "(uid=jdoe)"


def test_authenticate_wraps_parenthesized_extra_filter_with_and(patched_connection):
    bind_conn = _bind_connection([_user_entry("uid=jdoe,dc=example,dc=com")])
    user_conn = MagicMock(bound=True)
    patched_connection(bind_conn, user_conn)

    LdapService(
        _settings(search_filter="(memberOf=cn=staff,dc=example,dc=com)")
    ).authenticate("jdoe", "secret")

    assert (
        bind_conn.last_search_filter
        == "(&(uid=jdoe)(memberOf=cn=staff,dc=example,dc=com))"
    )


def test_authenticate_wraps_bare_extra_filter_in_parens(patched_connection):
    bind_conn = _bind_connection([_user_entry("uid=jdoe,dc=example,dc=com")])
    user_conn = MagicMock(bound=True)
    patched_connection(bind_conn, user_conn)

    LdapService(
        _settings(search_filter="memberOf=cn=staff,dc=example,dc=com")
    ).authenticate("jdoe", "secret")

    assert (
        bind_conn.last_search_filter
        == "(&(uid=jdoe)(memberOf=cn=staff,dc=example,dc=com))"
    )


def test_authenticate_rejects_empty_password_without_binding(patched_connection):
    connection_mock = patched_connection()

    result = LdapService(_settings()).authenticate("jdoe", "")

    assert result == {"success": False, "message": "Invalid credentials"}
    connection_mock.assert_not_called()


def test_authenticate_escapes_filter_metacharacters_in_username(
    patched_connection,
):
    bind_conn = _bind_connection([])
    patched_connection(bind_conn)

    LdapService(
        _settings(search_filter="(memberOf=cn=staff,dc=example,dc=com)")
    ).authenticate("jdoe)(|(uid=*", "secret")

    # The injected parentheses/wildcard must be escaped, not alter the
    # filter's logical structure.
    assert bind_conn.last_search_filter == (
        r"(&(uid=jdoe\29\28|\28uid=\2a)"
        "(memberOf=cn=staff,dc=example,dc=com))"
    )


def test_authenticate_denies_login_when_not_in_allowed_group(patched_connection):
    bind_conn = _bind_connection(
        [_user_entry("uid=jdoe,dc=example,dc=com", member_of=[])]
    )
    user_conn = MagicMock(bound=True)
    patched_connection(bind_conn, user_conn)

    result = LdapService(_settings(allowed_groups="opendox-user")).authenticate(
        "jdoe", "secret"
    )

    assert result == {
        "success": False,
        "message": "Not authorized (group restriction)",
    }


def test_authenticate_allows_login_when_in_allowed_group(patched_connection):
    bind_conn = _bind_connection(
        [
            _user_entry(
                "uid=jdoe,dc=example,dc=com",
                member_of=["cn=opendox-user,dc=example,dc=com"],
            )
        ]
    )
    user_conn = MagicMock(bound=True)
    patched_connection(bind_conn, user_conn)

    result = LdapService(_settings(allowed_groups="opendox-user")).authenticate(
        "jdoe", "secret"
    )

    assert result["success"] is True


def test_authenticate_maps_admin_group_to_admin_role(patched_connection):
    bind_conn = _bind_connection(
        [
            _user_entry(
                "uid=jdoe,dc=example,dc=com",
                member_of=["cn=opendox-admin,dc=example,dc=com"],
            )
        ]
    )
    user_conn = MagicMock(bound=True)
    patched_connection(bind_conn, user_conn)

    result = LdapService(_settings(admin_groups="opendox-admin")).authenticate(
        "jdoe", "secret"
    )

    assert result["role"] == "admin"


def test_authenticate_maps_moderator_group_to_moderator_role(patched_connection):
    bind_conn = _bind_connection(
        [
            _user_entry(
                "uid=jdoe,dc=example,dc=com",
                member_of=["cn=opendox-mod,dc=example,dc=com"],
            )
        ]
    )
    user_conn = MagicMock(bound=True)
    patched_connection(bind_conn, user_conn)

    result = LdapService(_settings(moderator_groups="opendox-mod")).authenticate(
        "jdoe", "secret"
    )

    assert result["role"] == "moderator"


def test_authenticate_admin_group_takes_precedence_over_moderator(
    patched_connection,
):
    bind_conn = _bind_connection(
        [
            _user_entry(
                "uid=jdoe,dc=example,dc=com",
                member_of=[
                    "cn=opendox-admin,dc=example,dc=com",
                    "cn=opendox-mod,dc=example,dc=com",
                ],
            )
        ]
    )
    user_conn = MagicMock(bound=True)
    patched_connection(bind_conn, user_conn)

    result = LdapService(
        _settings(admin_groups="opendox-admin", moderator_groups="opendox-mod")
    ).authenticate("jdoe", "secret")

    assert result["role"] == "admin"


def test_authenticate_group_matching_is_case_insensitive(patched_connection):
    bind_conn = _bind_connection(
        [
            _user_entry(
                "uid=jdoe,dc=example,dc=com",
                member_of=["CN=Opendox-Admin,DC=example,DC=com"],
            )
        ]
    )
    user_conn = MagicMock(bound=True)
    patched_connection(bind_conn, user_conn)

    result = LdapService(_settings(admin_groups="opendox-admin")).authenticate(
        "jdoe", "secret"
    )

    assert result["role"] == "admin"


def test_authenticate_denies_everyone_when_no_group_configured(patched_connection):
    bind_conn = _bind_connection(
        [
            _user_entry(
                "uid=jdoe,dc=example,dc=com",
                member_of=["cn=opendox-user,dc=example,dc=com"],
            )
        ]
    )
    patched_connection(bind_conn, MagicMock(bound=True))

    result = LdapService(_settings()).authenticate("jdoe", "secret")

    assert result["success"] is False


def test_authenticate_admin_group_member_may_log_in_without_allowed_group(
    patched_connection,
):
    bind_conn = _bind_connection(
        [
            _user_entry(
                "uid=jdoe,dc=example,dc=com",
                member_of=["cn=opendox-admin,dc=example,dc=com"],
            )
        ]
    )
    patched_connection(bind_conn, MagicMock(bound=True))

    result = LdapService(
        _settings(allowed_groups="opendox-user", admin_groups="opendox-admin")
    ).authenticate("jdoe", "secret")

    assert result["success"] is True
    assert result["role"] == "admin"


def test_authenticate_nested_group_resolved_via_matching_rule(patched_connection):
    bind_conn = _bind_connection(
        [
            _user_entry(
                "uid=jdoe,dc=example,dc=com",
                member_of=["cn=team-a,dc=example,dc=com"],
            )
        ]
    )
    patched_connection(bind_conn, MagicMock(bound=True))

    result = LdapService(
        _settings(allowed_groups="opendox-user", nested_groups=True)
    ).authenticate("jdoe", "secret")

    assert result["success"] is True
    assert (
        "memberOf:1.2.840.113556.1.4.1941:=cn=opendox-user,dc=example,dc=com"
        in bind_conn.last_search_filter
    )
    assert bind_conn.last_base_dn == "uid=jdoe,dc=example,dc=com"


def test_authenticate_nested_group_not_checked_when_disabled(patched_connection):
    bind_conn = _bind_connection(
        [
            _user_entry(
                "uid=jdoe,dc=example,dc=com",
                member_of=["cn=team-a,dc=example,dc=com"],
            )
        ]
    )
    patched_connection(bind_conn, MagicMock(bound=True))

    result = LdapService(_settings(allowed_groups="opendox-user")).authenticate(
        "jdoe", "secret"
    )

    assert result["success"] is False
    assert bind_conn.search.call_count == 1


def test_check_user_ok_returns_role(patched_connection):
    bind_conn = _bind_connection(
        [
            _user_entry(
                "uid=jdoe,dc=example,dc=com",
                member_of=["cn=opendox-admins,dc=example,dc=com"],
            )
        ]
    )
    patched_connection(bind_conn)
    service = LdapService(
        _settings(allowed_groups="opendox", admin_groups="opendox-admins")
    )

    assert service.check_user("jdoe") == {"status": "ok", "role": "admin"}
    bind_conn.unbind.assert_called_once()


def test_check_user_denied_when_not_found(patched_connection):
    patched_connection(_bind_connection([]))

    result = LdapService(_settings(allowed_groups="opendox")).check_user("jdoe")

    assert result["status"] == "denied"


def test_check_user_denied_when_group_removed(patched_connection):
    bind_conn = _bind_connection(
        [_user_entry("uid=jdoe,dc=example,dc=com", member_of=[])]
    )
    patched_connection(bind_conn)

    result = LdapService(_settings(allowed_groups="opendox")).check_user("jdoe")

    assert result["status"] == "denied"


def test_check_user_denied_when_ad_account_disabled(patched_connection):
    entry = _user_entry(
        "uid=jdoe,dc=example,dc=com",
        member_of=["cn=opendox,dc=example,dc=com"],
    )
    entry.userAccountControl = SimpleNamespace(value=512 | 0x2)
    patched_connection(_bind_connection([entry]))

    result = LdapService(_settings(allowed_groups="opendox")).check_user("jdoe")

    assert result == {"status": "denied", "message": "Account disabled"}


def test_check_user_unavailable_when_server_unreachable(patched_connection):
    patched_connection(Exception("connection refused"))

    result = LdapService(_settings(allowed_groups="opendox")).check_user("jdoe")

    assert result["status"] == "unavailable"


def test_check_user_unavailable_without_service_account(patched_connection):
    connection = patched_connection()

    result = LdapService(
        _settings(allowed_groups="opendox", bind_user_dn=None)
    ).check_user("jdoe")

    assert result["status"] == "unavailable"
    connection.assert_not_called()
