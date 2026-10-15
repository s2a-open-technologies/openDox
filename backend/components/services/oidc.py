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

import logging
from typing import Any
from urllib.parse import urljoin

import httpx
import jwt

logger = logging.getLogger(__name__)


class OidcDiscoveryError(Exception):
    """Raised when the OIDC discovery document cannot be fetched or parsed."""


class OidcService:
    """Thin client around an OpenID Connect provider using Authorization Code Flow.

    The service handles three concerns:

    1. **Discovery** — fetches ``{provider_url}/.well-known/openid-configuration`` once
       and caches the relevant endpoints (authorization, token, userinfo, jwks).
    2. **Authorization URL** — builds the redirect URL the browser navigates to,
       including a signed ``state`` and PKCE-less code challenge (we use
       ``client_secret_basic`` at the token endpoint instead).
    3. **Token exchange + userinfo** — exchanges the authorization code for
       access/id tokens, validates the id_token signature against the JWKS, and
       fetches the userinfo claims used for provisioning and group mapping.
    """

    def __init__(self, settings):
        self.settings = settings
        self._discovery: dict[str, Any] | None = None

    def _well_known_url(self) -> str:
        base = self.settings.provider_url.rstrip("/")
        return urljoin(base + "/", ".well-known/openid-configuration")

    def discover(self) -> dict[str, Any]:
        """Fetch and cache the OIDC discovery document.

        Returns:
            Parsed discovery JSON with at least ``authorization_endpoint``,
            ``token_endpoint``, ``userinfo_endpoint``, ``jwks_uri``.

        Raises:
            OidcDiscoveryError: If the provider is unreachable or the document
                is missing required endpoints.
        """
        if self._discovery is not None:
            return self._discovery
        try:
            resp = httpx.get(self._well_known_url(), timeout=10)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise OidcDiscoveryError(f"Discovery failed: {exc}") from exc
        doc = resp.json()
        for key in (
            "authorization_endpoint",
            "token_endpoint",
            "userinfo_endpoint",
            "jwks_uri",
        ):
            if key not in doc:
                raise OidcDiscoveryError(f"Discovery document missing '{key}'")
        self._discovery = doc
        return doc

    def authorization_url(self, redirect_uri: str, state: str) -> str:
        """Build the provider authorization endpoint URL with query params.

        Args:
            redirect_uri: Fully-qualified callback URL registered at the provider.
            state: Opaque state value signed by the caller (prevents CSRF).

        Returns:
            Absolute URL the browser should navigate to.
        """
        doc = self.discover()
        params = {
            "response_type": "code",
            "client_id": self.settings.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.settings.scopes,
            "state": state,
        }
        sep = "&" if "?" in doc["authorization_endpoint"] else "?"
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{doc['authorization_endpoint']}{sep}{query}"

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange an authorization code for token(s).

        Args:
            code: Authorization code returned by the provider.
            redirect_uri: Must match the one used in ``authorization_url``.

        Returns:
            Token response JSON (``access_token``, ``id_token``, ``expires_in``, ...).

        Raises:
            OidcDiscoveryError: If the token endpoint returns a non-200 response.
        """
        doc = self.discover()
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
        }
        try:
            resp = httpx.post(doc["token_endpoint"], data=data, timeout=10)
        except httpx.HTTPError as exc:
            raise OidcDiscoveryError(f"Token exchange failed: {exc}") from exc
        if resp.status_code != 200:
            raise OidcDiscoveryError(
                f"Token endpoint returned {resp.status_code}: {resp.text}"
            )
        return resp.json()

    def get_userinfo(self, access_token: str) -> dict[str, Any]:
        """Fetch userinfo claims with the access token.

        Args:
            access_token: Bearer token from the token exchange.

        Returns:
            Parsed userinfo JSON.

        Raises:
            OidcDiscoveryError: If the userinfo endpoint fails.
        """
        doc = self.discover()
        try:
            resp = httpx.get(
                doc["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
        except httpx.HTTPError as exc:
            raise OidcDiscoveryError(f"Userinfo fetch failed: {exc}") from exc
        if resp.status_code != 200:
            raise OidcDiscoveryError(
                f"Userinfo endpoint returned {resp.status_code}: {resp.text}"
            )
        return resp.json()

    def fetch_jwks(self) -> dict[str, Any]:
        """Fetch the JWKS document for id_token signature verification.

        Returns:
            JWKS JSON (``{"keys": [...]}``).
        """
        doc = self.discover()
        try:
            resp = httpx.get(doc["jwks_uri"], timeout=10)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise OidcDiscoveryError(f"JWKS fetch failed: {exc}") from exc
        return resp.json()

    def verify_id_token(self, id_token: str) -> dict[str, Any]:
        """Verify the id_token signature against the provider JWKS and return claims.

        Args:
            id_token: JWT returned by the token endpoint.

        Returns:
            Decoded claims dict from the id_token.
        """
        jwks = self.fetch_jwks()
        unverified_header = jwt.get_unverified_header(id_token)
        kid = unverified_header.get("kid")
        key = None
        for candidate in jwks.get("keys", []):
            if candidate.get("kid") == kid:
                key = candidate
                break
        if key is None:
            raise OidcDiscoveryError(f"No JWKS key matching kid={kid}")
        claims = jwt.decode(
            id_token,
            key=jwt.PyJWK(key).key,
            algorithms=["RS256", "ES256", "RS512"],
            audience=self.settings.client_id,
        )
        return claims

    def map_groups_to_role(self, claims: dict[str, Any]) -> str:
        """Resolve the local role from configured admin/moderator groups.

        Admin groups take precedence over moderator groups: a user in both
        becomes an admin.

        Args:
            claims: Union of id_token and userinfo claims.

        Returns:
            One of ``"admin"``, ``"moderator"``, ``"user"``.
        """
        user_groups = self._extract_groups(claims)
        admin_groups = self._parse_groups(self.settings.admin_groups)
        if admin_groups and (admin_groups & user_groups):
            return "admin"
        moderator_groups = self._parse_groups(self.settings.moderator_groups)
        if moderator_groups and (moderator_groups & user_groups):
            return "moderator"
        return "user"

    @staticmethod
    def _parse_groups(raw: str) -> set[str]:
        """Parse a comma-separated group list into a set of trimmed names."""
        if not raw:
            return set()
        return {g.strip() for g in raw.split(",") if g.strip()}

    def _extract_groups(self, claims: dict[str, Any]) -> set[str]:
        """Pull the configured group claim out of the claims, handling both
        list and comma-separated-string encodings.

        Args:
            claims: Decoded id_token / userinfo claims.

        Returns:
            Set of group names the user belongs to.
        """
        claim_name = self.settings.group_claim or "groups"
        raw = claims.get(claim_name)
        if raw is None:
            return set()
        if isinstance(raw, list):
            return {str(g) for g in raw}
        if isinstance(raw, str):
            return {g.strip() for g in raw.split(",") if g.strip()}
        return set()

    def resolve_username(self, claims: dict[str, Any]) -> str | None:
        """Resolve a stable local username from the claims using the configured claim.

        Args:
            claims: Decoded id_token / userinfo claims.

        Returns:
            Username string, or None if the claim is absent.
        """
        claim_name = self.settings.username_claim or "preferred_username"
        value = claims.get(claim_name)
        return str(value) if value is not None else None
