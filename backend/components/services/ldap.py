"""openDox - Medical transcription platform
Copyright (C) 2025  S2A Open Technologies gGmbH
SPDX-FileCopyrightText: 2025 S2A Open Technologies gGmbH
SPDX-License-Identifier: AGPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

# Standard library
import logging
import re
import ssl

# Third-party
from ldap3 import ALL, BASE, Connection, Server, Tls
from ldap3.utils.conv import escape_filter_chars

logger = logging.getLogger(__name__)

# Object classes a group entry may have: AD (group), OpenLDAP (groupOfNames,
# groupOfUniqueNames, posixGroup). Keeps a person whose cn equals a group name
# from being taken for the group.
_GROUP_CLASSES = (
    "(|(objectClass=group)(objectClass=groupOfNames)"
    "(objectClass=groupOfUniqueNames)(objectClass=posixGroup))"
)


def _parse_group_entries(raw: str | None) -> tuple[set[str], set[str]]:
    """Split a group field into plain group names and full DNs.

    Entries are separated by ``;`` or a line break. An entry containing ``=``
    is a full DN (its commas belong to the DN); any other entry is split once
    more at commas, so the old comma-separated name lists keep working.

    Args:
        raw: The configured field value.

    Returns:
        ``(names, dns)`` with names lower-cased and DNs normalised.
    """
    names: set[str] = set()
    dns: set[str] = set()
    for piece in re.split(r"[;\n]", raw or ""):
        piece = piece.strip()
        if not piece:
            continue
        if "=" in piece:
            dns.add(_normalize_dn(piece))
        else:
            names.update(n.strip().lower() for n in piece.split(",") if n.strip())
    return names, dns


def _normalize_dn(dn: str) -> str:
    """Lower-case a DN and drop the blanks around its separators."""
    rdns = re.split(r"(?<!\\),", dn)
    parts = []
    for rdn in rdns:
        attr, _, value = rdn.partition("=")
        parts.append(f"{attr.strip()}={value.strip()}")
    return ",".join(parts).lower()


# Active Directory LDAP_MATCHING_RULE_IN_CHAIN: the server resolves nested groups.
_AD_IN_CHAIN = "1.2.840.113556.1.4.1941"


# userAccountControl flag ACCOUNTDISABLE (Active Directory).
_ACCOUNT_DISABLED = 0x2


def _schema_has(conn, attribute: str) -> bool:
    """Tell whether the server schema knows ``attribute``."""
    schema = getattr(conn.server, "schema", None)
    return bool(schema) and attribute in schema.attribute_types


def _is_disabled(entry) -> bool:
    """Tell whether an Active Directory account is disabled."""
    raw = getattr(entry, "userAccountControl", None)
    value = getattr(raw, "value", raw)
    try:
        return bool(int(value) & _ACCOUNT_DISABLED)
    except (TypeError, ValueError):
        return False


class LdapService:
    """Service for authenticating users against an LDAP directory."""

    def __init__(self, settings):
        self.settings = settings

    def connect(self):
        """Open an (optionally TLS-secured) LDAP connection to the server."""
        tls_config = None
        if self.settings.use_ssl:
            cert_data = self.settings.cert_data or None
            tls_config = Tls(
                validate=ssl.CERT_REQUIRED if cert_data else ssl.CERT_NONE,
                ca_certs_data=cert_data,
            )

        server = Server(
            self.settings.server_host,
            port=self.settings.server_port,
            use_ssl=self.settings.use_ssl,
            get_info=ALL,
            tls=tls_config,
        )

        # If bind user provided, use it, else anonymous (or failure depending on server)
        user = self.settings.bind_user_dn
        password = self.settings.bind_user_password

        conn = Connection(server, user=user, password=password, auto_bind=True)
        return conn

    def _find_user(self, conn, username):
        """Search the user entry for ``username``; None if there is none."""
        # Build search filter: (user_dn=username) AND (search_filter)
        safe_username = escape_filter_chars(username)
        user_filter = f"({self.settings.user_dn}={safe_username})"
        extra = self.settings.search_filter
        if extra:
            extra = extra.strip()
            if extra.startswith("(") and extra.endswith(")"):
                search_filter = f"(&{user_filter}{extra})"
            else:
                search_filter = f"(&{user_filter}({extra}))"
        else:
            search_filter = user_filter

        attributes = [self.settings.user_dn, "memberOf"]
        # Only Active Directory has userAccountControl; ldap3 rejects attribute
        # names the server schema does not know, so ask for it only there.
        if _schema_has(conn, "userAccountControl"):
            attributes.append("userAccountControl")
        conn.search(self.settings.base_dn, search_filter, attributes=attributes)
        return conn.entries[0] if conn.entries else None

    def _find_groups(self, conn, names):
        """Look up group names below ``base_dn``; returns ``{name: {dn, ...}}``.

        A name matches the group's ``cn`` and, on Active Directory, also its
        ``sAMAccountName`` (the "pre-Windows 2000" name admins usually know,
        which may differ from the cn). ldap3 rejects attribute names the server
        schema does not know, so ``sAMAccountName`` is only used where it exists.
        """
        found: dict[str, set[str]] = {name: set() for name in names}
        if not names:
            return found
        attrs = ["cn"]
        if _schema_has(conn, "sAMAccountName"):
            attrs.append("sAMAccountName")
        name_filter = "".join(
            f"({attr}={escape_filter_chars(n)})"
            for n in sorted(names)
            for attr in attrs
        )
        conn.search(
            self.settings.base_dn,
            f"(&{_GROUP_CLASSES}(|{name_filter}))",
            attributes=attrs,
        )
        for group in conn.entries:
            keys = set()
            for attr in attrs:
                values = getattr(group, attr, None)
                keys.update(str(v).lower() for v in (values.values if values else []))
            for key in keys & found.keys():
                found[key].add(_normalize_dn(group.entry_dn))
        return found

    def _configured_group_dns(self, conn):
        """Resolve the three group fields to sets of group DNs.

        A full DN is taken as it is. A name is searched (as cn, on Active
        Directory also as sAMAccountName) in the whole subtree below
        ``base_dn``, so the group may sit in any OU. A name that is not
        found falls back to ``cn=<name>,<base_dn>`` (the old rule, in case the
        service account may not search groups); a name that matches several
        groups counts for none of them, since a same-named group elsewhere must
        not grant access — the admin has to enter the full DN then.
        """
        fields = [
            _parse_group_entries(self.settings.allowed_groups),
            _parse_group_entries(self.settings.admin_groups),
            _parse_group_entries(self.settings.moderator_groups),
        ]
        all_names = set().union(*(names for names, _ in fields))
        found = self._find_groups(conn, all_names)
        resolved: dict[str, set[str]] = {}
        for name, dns in found.items():
            if len(dns) > 1:
                logger.warning(
                    "LDAP group name %r is ambiguous (%d groups); ignored, "
                    "enter the full DN instead",
                    name,
                    len(dns),
                )
                resolved[name] = set()
            elif dns:
                resolved[name] = dns
            else:
                logger.warning(
                    "LDAP group %r not found below the base DN "
                    "(searched cn, on Active Directory also sAMAccountName)",
                    name,
                )
                resolved[name] = {_normalize_dn(f"cn={name},{self.settings.base_dn}")}
        return tuple(
            set(dns).union(*(resolved[n] for n in names)) for names, dns in fields
        )

    def _resolve_role(self, conn, entry):
        """Map the entry's group membership to a role; None if not permitted."""
        user_dn = entry.entry_dn
        member_of = getattr(entry, "memberOf", None)
        member_of_values = member_of.values if member_of else []
        user_group_dns = {_normalize_dn(v) for v in member_of_values}

        allowed_dns, admin_dns, moderator_dns = self._configured_group_dns(conn)
        if getattr(self.settings, "nested_groups", False):
            # Active Directory only: memberOf lists direct groups, so ask
            # the server per configured group whether the user is a
            # (transitive) member.
            for group_dn in allowed_dns | admin_dns | moderator_dns:
                if group_dn in user_group_dns:
                    continue
                conn.search(
                    user_dn,
                    f"(memberOf:{_AD_IN_CHAIN}:={escape_filter_chars(group_dn)})",
                    search_scope=BASE,
                    attributes=["distinguishedName"],
                )
                if conn.entries:
                    user_group_dns.add(group_dn)

        # Fail closed: only members of an allowed, admin or moderator group
        # may log in. With no group configured nobody may.
        if not ((allowed_dns | admin_dns | moderator_dns) & user_group_dns):
            return None
        if admin_dns & user_group_dns:
            return "admin"
        if moderator_dns & user_group_dns:
            return "moderator"
        return "user"

    def authenticate(self, username, password):
        """Authenticate a user and determine their role from group membership."""
        if not password or not password.strip():
            # RFC 4513 "unauthenticated bind": a SIMPLE bind with a non-empty
            # DN and an empty password is treated by ldap3/many servers as a
            # successful anonymous bind, not a credential check. Reject it
            # up front rather than letting it reach the LDAP server.
            return {"success": False, "message": "Invalid credentials"}

        try:
            conn = self.connect()

            entry = self._find_user(conn, username)
            if entry is None:
                return {"success": False, "message": "User not found"}

            # Attempt bind with user credentials
            user_conn = Connection(
                conn.server, user=entry.entry_dn, password=password, auto_bind=True
            )
            if not user_conn.bound:
                conn.unbind()
                return {"success": False, "message": "Invalid credentials"}

            user_conn.unbind()

            role = self._resolve_role(conn, entry)
            conn.unbind()

            if role is None:
                return {
                    "success": False,
                    "message": "Not authorized (group restriction)",
                }

            return {
                "success": True,
                "message": "Authentication successful",
                "role": role,
            }

        except Exception as e:
            return {"success": False, "message": str(e)}

    def check_user(self, username):
        """Re-check a logged-in user against the directory, without a password.

        Used when a session is renewed: binds with the service account only and
        looks at whether the account still exists, is not disabled (Active
        Directory) and is still in a permitted group.

        Args:
            username: The local user name (same value the user logged in with).

        Returns:
            ``{"status": "ok", "role": ...}``, ``{"status": "denied", "message"}``
            if the directory says no, or ``{"status": "unavailable", "message"}``
            if it could not be asked (no service account, server unreachable).
        """
        if not self.settings.bind_user_dn:
            return {"status": "unavailable", "message": "No service account"}
        try:
            conn = self.connect()
        except Exception as e:
            return {"status": "unavailable", "message": str(e)}
        try:
            entry = self._find_user(conn, username)
            if entry is None:
                return {"status": "denied", "message": "User not found"}
            if _is_disabled(entry):
                return {"status": "denied", "message": "Account disabled"}
            role = self._resolve_role(conn, entry)
        except Exception as e:
            return {"status": "unavailable", "message": str(e)}
        finally:
            conn.unbind()
        if role is None:
            return {"status": "denied", "message": "Not authorized (group restriction)"}
        return {"status": "ok", "role": role}
