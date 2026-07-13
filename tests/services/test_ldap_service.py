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
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _bind_connection(entries):
    """Fake service-account connection returned by the first Connection() call."""
    conn = MagicMock()
    conn.server = "fake-server"

    def fake_search(base_dn, search_filter, attributes=None):
        conn.entries = entries
        conn.last_search_filter = search_filter
        conn.last_base_dn = base_dn

    conn.search.side_effect = fake_search
    conn.entries = []
    return conn


def _user_entry(dn):
    return SimpleNamespace(entry_dn=dn)


@pytest.fixture
def patched_connection(monkeypatch):
    """Returns a helper to queue up Connection() return values / side effects."""

    def install(*connections):
        mock_connection = MagicMock(side_effect=list(connections))
        monkeypatch.setattr(ldap_module, "Connection", mock_connection)
        return mock_connection

    return install


def test_authenticate_succeeds_with_valid_credentials(patched_connection):
    bind_conn = _bind_connection([_user_entry("uid=jdoe,dc=example,dc=com")])
    user_conn = MagicMock()
    user_conn.bound = True
    patched_connection(bind_conn, user_conn)

    result = LdapService(_settings()).authenticate("jdoe", "secret")

    assert result == {"success": True, "message": "Authentication successful"}
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
