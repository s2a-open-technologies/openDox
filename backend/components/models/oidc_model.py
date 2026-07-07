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

from typing import Optional

from sqlmodel import Field, SQLModel


class OidcSettingsModel(SQLModel, table=True):
    """Configuration for an OpenID Connect provider (Authorization Code Flow).

    All endpoint URLs are fetched via discovery from ``{provider_url}/.well-known/openid-configuration``;
    only the issuer base URL needs to be configured here.

    Attributes:
        provider_url: Issuer base URL, e.g. ``https://keycloak.example.com/realms/myrealm``.
        client_id: OAuth/OIDC client id registered at the provider.
        client_secret: Client secret for the confidential Authorization Code Flow.
        scopes: Space-separated OIDC scopes (default ``openid email profile``).
        group_claim: Name of the claim in the id_token / userinfo response that
            contains the user's group memberships. Defaults to ``groups``.
        admin_groups: Comma-separated group names that map to ``is_superuser=True``.
        username_claim: Claim used to derive the local ``User.name``. Defaults to ``preferred_username``.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    enabled: bool = Field(default=False)
    provider_url: str = Field(default="")
    client_id: str = Field(default="")
    client_secret: str = Field(default="")
    scopes: str = Field(default="openid email profile")
    group_claim: str = Field(default="groups")
    admin_groups: str = Field(default="")
    username_claim: str = Field(default="preferred_username")
