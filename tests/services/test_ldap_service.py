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


def _bind_connection(entries, groups=None):
    """Fake service-account connection returned by the first Connection() call.

    ``groups`` lists ``(dn, cn)`` or ``(dn, cn, sAMAccountName)`` entries;
    the group-name lookup (a search for group object classes) gets those whose
    cn or sAMAccountName is in the filter, every other search gets ``entries``.
    """
    conn = MagicMock()
    conn.server = "fake-server"
    conn.filters = []

    def fake_search(base_dn, search_filter, attributes=None, **kwargs):
        conn.filters.append(search_filter)
        conn.last_search_filter = search_filter
        conn.last_base_dn = base_dn
        if "objectClass=group" in search_filter:
            conn.entries = []
            for group in groups or []:
                dn, cn, sam = (*group, None)[:3]
                hit = f"(cn={cn})".lower() in search_filter.lower() or (
                    sam and f"(samaccountname={sam})".lower() in search_filter.lower()
                )
                if hit:
                    entry = SimpleNamespace(
                        entry_dn=dn, cn=SimpleNamespace(values=[cn])
                    )
                    if sam:
                        entry.sAMAccountName = SimpleNamespace(values=[sam])
                    conn.entries.append(entry)
        else:
            conn.entries = entries

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
    assert not any("1.2.840.113556.1.4.1941" in f for f in bind_conn.filters)


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


def _login(patched_connection, member_of, groups=None, **settings):
    bind_conn = _bind_connection(
        [_user_entry("uid=jdoe,dc=example,dc=com", member_of=member_of)], groups
    )
    patched_connection(bind_conn, MagicMock(bound=True))
    return LdapService(_settings(**settings)).authenticate("jdoe", "secret"), bind_conn


def test_group_name_found_deep_in_the_tree(patched_connection):
    deep = "CN=opendox-admin,OU=Gruppen,OU=Klinik,DC=example,DC=com"
    result, bind_conn = _login(
        patched_connection,
        [deep],
        groups=[(deep, "opendox-admin")],
        admin_groups="opendox-admin",
    )

    assert result["role"] == "admin"
    assert any(
        "objectClass=group" in f and "(cn=opendox-admin)" in f
        for f in bind_conn.filters
    )


def test_full_dn_outside_base_dn_matches(patched_connection):
    result, _ = _login(
        patched_connection,
        ["CN=opendox,OU=Apps,DC=other,DC=org"],
        allowed_groups="cn=opendox, ou=Apps, dc=other, dc=org",
    )

    assert result["success"] is True
    assert result["role"] == "user"


def test_full_dns_and_names_separated_by_semicolon(patched_connection):
    result, _ = _login(
        patched_connection,
        ["cn=mods,ou=x,dc=example,dc=com"],
        groups=[("cn=mods,ou=x,dc=example,dc=com", "mods")],
        allowed_groups="cn=a,ou=y,dc=example,dc=com; b, c",
        moderator_groups="mods",
    )

    assert result["role"] == "moderator"


def test_ambiguous_group_name_grants_nothing(patched_connection):
    real = "cn=opendox-admin,ou=gruppen,dc=example,dc=com"
    fake = "cn=opendox-admin,ou=sandbox,dc=example,dc=com"
    result, _ = _login(
        patched_connection,
        [fake],
        groups=[(real, "opendox-admin"), (fake, "opendox-admin")],
        admin_groups="opendox-admin",
    )

    assert result["success"] is False


def test_unknown_group_name_falls_back_to_base_dn_rule(patched_connection):
    result, _ = _login(
        patched_connection,
        ["cn=opendox-user,dc=example,dc=com"],
        groups=[],
        allowed_groups="opendox-user",
    )

    assert result["success"] is True


def test_group_in_other_ou_with_unknown_name_is_denied(patched_connection):
    result, _ = _login(
        patched_connection,
        ["cn=opendox-user,ou=gruppen,dc=example,dc=com"],
        groups=[],
        allowed_groups="opendox-user",
    )

    assert result["success"] is False


def test_nested_check_uses_resolved_group_dn(patched_connection):
    deep = "cn=opendox-user,ou=gruppen,dc=example,dc=com"
    result, bind_conn = _login(
        patched_connection,
        ["cn=team-a,dc=example,dc=com"],
        groups=[(deep, "opendox-user")],
        allowed_groups="opendox-user",
        nested_groups=True,
    )

    assert result["success"] is True
    assert bind_conn.last_search_filter == (
        "(memberOf:1.2.840.113556.1.4.1941:=" + deep + ")"
    )


@pytest.fixture
def active_directory(monkeypatch):
    """Pretend the server schema is Active Directory's (knows sAMAccountName)."""
    monkeypatch.setattr(
        ldap_module, "_schema_has", lambda conn, attr: attr == "sAMAccountName"
    )


def test_group_found_by_sam_account_name_on_ad(patched_connection, active_directory):
    dn = "cn=opendox benutzer,ou=gruppen,dc=example,dc=com"
    result, bind_conn = _login(
        patched_connection,
        [dn],
        groups=[(dn, "openDox Benutzer", "opendox-user")],
        allowed_groups="opendox-user",
    )

    assert result["success"] is True
    assert any("(sAMAccountName=opendox-user)" in f for f in bind_conn.filters)


def test_sam_account_name_not_searched_without_ad_schema(patched_connection):
    dn = "cn=opendox benutzer,ou=gruppen,dc=example,dc=com"
    result, bind_conn = _login(
        patched_connection,
        [dn],
        groups=[(dn, "openDox Benutzer", "opendox-user")],
        allowed_groups="opendox-user",
    )

    assert result["success"] is False
    assert not any("sAMAccountName" in f for f in bind_conn.filters)


def test_cn_of_one_and_sam_of_another_group_is_ambiguous(
    patched_connection, active_directory
):
    a = "cn=opendox-admin,ou=gruppen,dc=example,dc=com"
    b = "cn=sandbox,ou=test,dc=example,dc=com"
    result, _ = _login(
        patched_connection,
        [a],
        groups=[(a, "opendox-admin", "oda"), (b, "sandbox", "opendox-admin")],
        admin_groups="opendox-admin",
    )

    assert result["success"] is False


@pytest.mark.parametrize(
    "raw, names, dns",
    [
        (None, set(), set()),
        ("a, B", {"a", "b"}, set()),
        ("a\nb", {"a", "b"}, set()),
        (
            "CN=x, OU=y,DC=z; a",
            {"a"},
            {"cn=x,ou=y,dc=z"},
        ),
        (r"cn=Doe\, John,dc=z", set(), {r"cn=doe\, john,dc=z"}),
    ],
)
def test_parse_group_entries(raw, names, dns):
    assert ldap_module._parse_group_entries(raw) == (names, dns)
