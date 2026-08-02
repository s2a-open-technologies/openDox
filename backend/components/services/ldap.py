"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

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

import ssl

from ldap3 import ALL, Connection, Server, Tls
from ldap3.utils.conv import escape_filter_chars


def _parse_groups(raw: str | None) -> set[str]:
    """Parse a comma-separated group-name list into a set of trimmed names."""
    if not raw:
        return set()
    return {name.strip() for name in raw.split(",") if name.strip()}


def _group_dn(name: str, base_dn: str) -> str:
    """Build the expected DN for a group name directly under ``base_dn``."""
    return f"cn={name},{base_dn}"


class LdapService:
    def __init__(self, settings):
        self.settings = settings

    def connect(self):
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

    def authenticate(self, username, password):
        if not password or not password.strip():
            # RFC 4513 "unauthenticated bind": a SIMPLE bind with a non-empty
            # DN and an empty password is treated by ldap3/many servers as a
            # successful anonymous bind, not a credential check. Reject it
            # up front rather than letting it reach the LDAP server.
            return {"success": False, "message": "Invalid credentials"}

        try:
            conn = self.connect()

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

            conn.search(
                self.settings.base_dn,
                search_filter,
                attributes=[self.settings.user_dn, "memberOf"],
            )

            if not conn.entries:
                return {"success": False, "message": "User not found"}

            entry = conn.entries[0]
            user_dn = entry.entry_dn
            member_of = getattr(entry, "memberOf", None)
            member_of_values = member_of.values if member_of else []
            user_group_dns = {v.lower() for v in member_of_values}

            # Attempt bind with user credentials
            user_conn = Connection(
                conn.server, user=user_dn, password=password, auto_bind=True
            )
            if not user_conn.bound:
                conn.unbind()
                return {"success": False, "message": "Invalid credentials"}

            user_conn.unbind()
            conn.unbind()

            allowed_dns = {
                _group_dn(name, self.settings.base_dn).lower()
                for name in _parse_groups(self.settings.allowed_groups)
            }
            if allowed_dns and not (allowed_dns & user_group_dns):
                return {
                    "success": False,
                    "message": "Not authorized (group restriction)",
                }

            admin_dns = {
                _group_dn(name, self.settings.base_dn).lower()
                for name in _parse_groups(self.settings.admin_groups)
            }
            moderator_dns = {
                _group_dn(name, self.settings.base_dn).lower()
                for name in _parse_groups(self.settings.moderator_groups)
            }
            if admin_dns & user_group_dns:
                role = "admin"
            elif moderator_dns & user_group_dns:
                role = "moderator"
            else:
                role = "user"

            return {
                "success": True,
                "message": "Authentication successful",
                "role": role,
            }

        except Exception as e:
            return {"success": False, "message": str(e)}
