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

import secrets
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer
from sqlmodel import select

from backend.components.models.oidc_model import OidcSettingsModel
from backend.components.models.user_model import User
from backend.components.modules.env import env_or_file
from backend.components.security.hashing import (
    create_access_token,
    create_refresh_token,
)
from backend.components.services.oidc import OidcDiscoveryError, OidcService
from backend.components.sql.sql_engine import SessionDep

oidc_bp = APIRouter(prefix="/api/v1/auth/oidc", tags=["auth"])

# Itsdangerous signer for the OIDC ``state`` cookie. Signed with the app JWT
# secret so a forged state would require leaking SECRET_KEY. The serializer is
# stateless (purely string-based), so it works across processes and restarts.
_serializer = URLSafeSerializer(
    env_or_file("SECRET_KEY", "TestintDebugKey"), salt="oidc-state"
)
_STATE_COOKIE = "oidc_state"
_STATE_TTL = 600  # seconds


def _build_redirect_uri(request: Request) -> str:
    """Build the absolute callback URL from the incoming request.

    Honours ``X-Forwarded-Proto`` and ``X-Forwarded-Host`` so it works behind a
    reverse proxy (Apache, nginx, Traefik). ROOT_PATH is read from the env so
    the callback path matches how the router is mounted.

    Args:
        request: The incoming FastAPI request.

    Returns:
        Absolute URL like ``https://opendox.example.com/opendox/api/v1/auth/oidc/callback``.
    """
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get(
        "x-forwarded-host", request.headers.get("host", request.url.netloc)
    )
    root_path = (env_or_file("ROOT_PATH", "") or "").rstrip("/")
    return f"{proto}://{host}{root_path}/api/v1/auth/oidc/callback"


def _get_settings(db: SessionDep) -> Optional[OidcSettingsModel]:
    """Return the OIDC settings row, or None if not yet configured."""
    return db.exec(select(OidcSettingsModel)).first()


@oidc_bp.get("/login")
async def oidc_login(request: Request, db: SessionDep):
    """Redirect the browser to the OIDC provider authorization endpoint.

    The ``state`` is signed and stored in a short-lived cookie, so we can verify
    the callback is the one we initiated (CSRF protection).

    Args:
        request: Incoming FastAPI request (used to build the redirect URI).
        db: Database session.

    Raises:
        HTTPException: 503 if OIDC is disabled or misconfigured.
    """
    settings = _get_settings(db)
    if not settings or not settings.enabled:
        raise HTTPException(status_code=503, detail="OIDC nicht konfiguriert")

    try:
        service = OidcService(settings)
        redirect_uri = _build_redirect_uri(request)
        state = secrets.token_urlsafe(32)
        signed_state = _serializer.dumps({"state": state})
        auth_url = service.authorization_url(redirect_uri, state)
    except OidcDiscoveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    response = RedirectResponse(url=auth_url, status_code=302)
    response.set_cookie(
        key=_STATE_COOKIE,
        value=signed_state,
        max_age=_STATE_TTL,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
    )
    return response


@oidc_bp.get("/callback")
async def oidc_callback(request: Request, db: SessionDep):
    """Handle the redirect back from the OIDC provider.

    Verifies state, exchanges the code for tokens, fetches userinfo, provisions
    the user, and redirects to the frontend with tokens in query params (since
    the SPA cannot read cookies set during a cross-site redirect).

    Args:
        request: Incoming FastAPI request.
        db: Database session.

    Raises:
        HTTPException: 400 on state mismatch, 502 on provider errors.
    """
    settings = _get_settings(db)
    if not settings or not settings.enabled:
        raise HTTPException(status_code=503, detail="OIDC nicht konfiguriert")

    # --- 1. Verify state cookie matches query state (CSRF) ---
    cookie_state = request.cookies.get(_STATE_COOKIE)
    query_state = request.query_params.get("state")
    if not cookie_state or not query_state:
        raise HTTPException(status_code=400, detail="State fehlt")
    try:
        decoded = _serializer.loads(cookie_state, max_age=_STATE_TTL)
    except BadSignature as exc:
        raise HTTPException(status_code=400, detail="State ungültig") from exc
    if decoded.get("state") != query_state:
        raise HTTPException(status_code=400, detail="State mismatch")

    # --- 2. Exchange authorization code for tokens ---
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Code fehlt")
    try:
        service = OidcService(settings)
        redirect_uri = _build_redirect_uri(request)
        token_data = service.exchange_code(code, redirect_uri)
    except OidcDiscoveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    id_token = token_data.get("id_token")
    access_token = token_data.get("access_token", "")
    if not id_token:
        raise HTTPException(status_code=502, detail="Kein id_token erhalten")

    # --- 3. Verify id_token + fetch userinfo (claims union) ---
    try:
        claims = service.verify_id_token(id_token)
    except OidcDiscoveryError as exc:
        raise HTTPException(
            status_code=502, detail=f"Token-Validierung fehlgeschlagen: {exc}"
        ) from exc
    try:
        userinfo = service.get_userinfo(access_token)
    except OidcDiscoveryError:
        userinfo = {}
    claims = {**userinfo, **claims}

    username = service.resolve_username(claims)
    if not username:
        raise HTTPException(status_code=502, detail="Kein Benutzername im Claim")

    # --- 4. Provision / update user ---
    user = db.exec(select(User).where(User.name == username)).first()
    role = service.map_groups_to_role(claims)
    if not user:
        user = User(
            name=username,
            hashed_password="",
            is_active=True,
            role=role,
        )
        db.add(user)
    else:
        user.is_active = True
        user.role = role
    db.commit()
    db.refresh(user)

    # --- 5. Issue local tokens + redirect to frontend ---
    local_access = create_access_token(sub=str(user.id))
    local_refresh = create_refresh_token(sub=str(user.id))
    root_path = (env_or_file("ROOT_PATH", "") or "").rstrip("/")
    # Use fragment so tokens never hit server logs / proxies, matching OAuth 2.1
    redirect_url = (
        f"{root_path}/login?access_token={local_access}&refresh_token={local_refresh}"
    )
    response = RedirectResponse(url=redirect_url, status_code=302)
    response.delete_cookie(_STATE_COOKIE)
    return response


@oidc_bp.get("/status")
async def oidc_status(db: SessionDep):
    """Tell the frontend whether OIDC login is offered.

    Returns:
        ``{"enabled": bool}``. The frontend uses this to show/hide the SSO button.
    """
    settings = _get_settings(db)
    return {"enabled": bool(settings and settings.enabled)}
