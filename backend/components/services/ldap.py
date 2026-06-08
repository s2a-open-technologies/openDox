"""
  openDox - Medical transcription platform
  Copyright (C) 2025  crizz <christopher.abanilla@gmx.de>

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

from ldap3 import Server, Connection, ALL, SUBTREE, EXTERNAL, SIMPLE, Tls
import ssl
import os

class LdapService:
    def __init__(self, settings):
        self.settings = settings

    def connect(self):
        tls_config = None
        if self.settings.use_ssl:
            ca_certs_file = None
            if self.settings.cert_filename:
                # Assuming certs are stored in 'certs' directory in app root or similar
                # Just define abstract logic for now
                cert_path = os.path.join(os.getcwd(), 'certs', self.settings.cert_filename)
                if os.path.exists(cert_path):
                    ca_certs_file = cert_path
            
            tls_config = Tls(validate=ssl.CERT_REQUIRED if ca_certs_file else ssl.CERT_NONE, 
                             ca_certs_file=ca_certs_file)

        server = Server(
            self.settings.server_host,
            port=self.settings.server_port,
            use_ssl=self.settings.use_ssl,
            get_info=ALL,
            tls=tls_config
        )
        
        # If bind user provided, use it, else anonymous (or failure depending on server)
        user = self.settings.bind_user_dn
        password = self.settings.bind_user_password
        
        conn = Connection(server, user=user, password=password, auto_bind=True)
        return conn

    def authenticate(self, username, password):
        try:
            conn = self.connect()
            
            # Search for user
            search_filter = f"({self.settings.user_dn}={username})"
            conn.search(self.settings.base_dn, search_filter, attributes=[self.settings.user_dn])
            
            if not conn.entries:
                 return {"success": False, "message": "User not found"}
            
            user_dn = conn.entries[0].entry_dn
            
            # Attempt bind with user credentials
            user_conn = Connection(conn.server, user=user_dn, password=password, auto_bind=True)
            if user_conn.bound:
                user_conn.unbind()
                conn.unbind()
                return {"success": True, "message": "Authentication successful"}
            else:
                conn.unbind()
                return {"success": False, "message": "Invalid credentials"}
                
        except Exception as e:
            return {"success": False, "message": str(e)}
