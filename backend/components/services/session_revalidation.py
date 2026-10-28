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
from typing import Literal

# Third-party
from sqlmodel import Session, select

# Custom
from backend.components.models.ldap_model import LdapSettingsModel
from backend.components.models.oidc_model import OidcSettingsModel
from backend.components.models.user_model import User
from backend.components.modules.logger import get_logger
from backend.components.services.audit_service import audit
from backend.components.services.ldap import LdapService
from backend.components.services.oidc import OidcService

logger = get_logger(__name__)


def revalidate_user(db: Session, user: User) -> Literal["ok", "denied"]:
    """Re-check a user against their login source when a session is renewed.

    Local users need nothing beyond ``is_active`` (checked by the caller).
    LDAP users are looked up with the service account, OIDC users are renewed
    at the provider; either way the role follows the current group
    membership, as it does on login. If the source cannot be asked (server
    down, no service account, no provider refresh token) the session is kept:
    a directory outage must not log everyone out in the middle of a dictation.
    Only a definite answer (account gone, disabled, out of every permitted
    group, provider refuses) ends it.

    Args:
        db: Database session; role and provider token changes are committed.
        user: The active user renewing their session.

    Returns:
        ``"ok"`` to issue new tokens, ``"denied"`` to refuse the renewal.
    """
    if user.auth_source == "ldap":
        settings = db.exec(select(LdapSettingsModel)).first()
        if settings is None:
            logger.info("Session of %s ended: LDAP is not configured", user.name)
            return "denied"
        result = LdapService(settings).check_user(user.name)
    elif user.auth_source == "oidc":
        settings = db.exec(select(OidcSettingsModel)).first()
        if settings is None or not settings.enabled:
            logger.info("Session of %s ended: OIDC is disabled", user.name)
            return "denied"
        if not user.idp_refresh_token:
            logger.warning(
                "Cannot re-check %s at the OIDC provider: it returned no refresh "
                "token at login (add the offline_access scope if it needs one)",
                user.name,
            )
            return "ok"
        result = OidcService(settings).refresh(user.idp_refresh_token)
        if result["status"] == "ok":
            user.idp_refresh_token = result["refresh_token"]
    else:
        return "ok"

    if result["status"] == "denied":
        logger.info(
            "Session of %s ended by %s: %s",
            user.name,
            user.auth_source,
            result.get("message"),
        )
        return "denied"
    if result["status"] == "unavailable":
        logger.warning(
            "Cannot re-check %s against %s, keeping the session: %s",
            user.name,
            user.auth_source,
            result.get("message"),
        )
        return "ok"

    if user.role != result["role"]:
        audit(
            db,
            "user.role_sync",
            actor=user,
            target_type="user",
            target_id=user.id,
            details={
                "from": user.role,
                "to": result["role"],
                "source": user.auth_source,
            },
        )
    user.role = result["role"]
    db.add(user)
    db.commit()
    return "ok"
