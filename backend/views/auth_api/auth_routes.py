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

# routers/auth.py
from datetime import datetime, timezone
from typing import Optional

from fastapi import Body, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlmodel import select

from backend.components.models.ldap_model import LdapSettingsModel
from backend.components.models.token_model import Token
from backend.components.models.user_model import (
    ROLES,
    User,
    UserCreate,
    UserLogin,
    UserRead,
    UserUpdate,
)
from backend.components.modules.api_errors import api_error
from backend.components.security.hashing import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from backend.components.services.audit_service import audit, changed_fields
from backend.components.services.ldap import LdapService
from backend.components.services.rate_limiter import login_limiter
from backend.components.services.session_revalidation import revalidate_user
from backend.components.sql.sql_engine import SessionDep
from backend.views.auth_api import auth_bp
from backend.views.auth_api.dependencies import get_current_user

# ── Authentication ──────────────────────────────────────────────────────


def _reject_locked(user: User) -> None:
    """Refuse a login for an account an admin locked in openDox.

    Only called after the credentials were verified, so the lock is never
    revealed to someone without the password. A directory login does not undo
    the lock: access is revoked by removing the group, or here in the app.
    """
    if not user.is_active:
        raise api_error(403, "account_locked", "Account locked")


# Audit reason per status code of a refused login.
_LOGIN_FAILURE_REASONS = {
    401: "invalid_credentials",
    403: "account_locked",
    429: "rate_limited",
}


@auth_bp.post("/login", response_model=Token)
async def login(request: Request, user_in: UserLogin, db: SessionDep):
    """Authenticate via local DB or LDAP and return a token pair.

    Every refused login is written to the audit log (successful ones are not).
    """
    try:
        return _authenticate(request, user_in, db)
    except HTTPException as exc:
        # Nothing of a refused login may be persisted except the audit entry.
        db.rollback()
        audit(
            db,
            "auth.login",
            request=request,
            actor_name=user_in.name,
            outcome="denied" if exc.status_code in (403, 429) else "failure",
            details={
                "reason": _LOGIN_FAILURE_REASONS.get(exc.status_code, "error"),
            },
            commit=True,
        )
        raise


def _authenticate(request: Request, user_in: UserLogin, db: SessionDep) -> Token:
    login_limiter.check(request)

    # Check if user exists and password is correct
    stmt = select(User).where(User.name == user_in.name)
    user = db.exec(stmt).first()

    # 1. Local Login
    if user and user.hashed_password:
        if verify_password(user_in.password, user.hashed_password):
            _reject_locked(user)
            if user.auth_source != "local":
                user.auth_source = "local"
                db.add(user)
                db.commit()
            access_token = create_access_token(sub=str(user.id))
            refresh_token = create_refresh_token(sub=str(user.id))
            return Token(access_token=access_token, refresh_token=refresh_token)

    # 2. LDAP Login (if local failed or user not found)
    # Check if LDAP is configured
    stmt_ldap = select(LdapSettingsModel)
    ldap_settings = db.exec(stmt_ldap).first()

    if ldap_settings:
        ldap_service = LdapService(ldap_settings)
        auth_result = ldap_service.authenticate(user_in.name, user_in.password)

        if auth_result["success"]:
            role = auth_result.get("role", "user")
            # Sync user to DB
            if not user:
                user = User(
                    name=user_in.name,
                    hashed_password="",  # No password for LDAP users
                    is_active=True,
                    role=role,
                    auth_source="ldap",
                )
                db.add(user)

            else:
                _reject_locked(user)
                # Re-sync the role from current LDAP group membership.
                if user.role != role:
                    audit(
                        db,
                        "user.role_sync",
                        request=request,
                        actor=user,
                        target_type="user",
                        target_id=user.id,
                        details={"from": user.role, "to": role, "source": "ldap"},
                    )
                user.role = role
                user.auth_source = "ldap"

            db.commit()
            db.refresh(user)

            access_token = create_access_token(sub=str(user.id))
            refresh_token = create_refresh_token(sub=str(user.id))
            return Token(access_token=access_token, refresh_token=refresh_token)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect name or password",
    )


class RefreshIn(BaseModel):
    """Request body for ``/refresh``."""

    refresh_token: str


@auth_bp.post("/refresh", response_model=Token)
async def refresh_token_endpoint(
    db: SessionDep,
    body: Optional[RefreshIn] = Body(default=None),
    refresh_token: Optional[str] = None,
):
    """Issue a new token pair for a valid refresh token.

    The token belongs in the JSON body; the query parameter is only accepted
    for older desktop clients, since URLs end up in proxy access logs.

    The user must still exist and be active, and LDAP/OIDC users are re-checked
    against their directory (``session_revalidation.revalidate_user``), so a
    revoked account loses access within one access-token lifetime.
    """
    refresh_token = body.refresh_token if body else refresh_token
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
        )
    try:
        payload = decode_token(refresh_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("token_type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user = db.get(User, int(sub))
    except ValueError:
        user = None
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    if revalidate_user(db, user) == "denied":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access revoked",
        )

    return Token(
        access_token=create_access_token(sub=sub),
        refresh_token=create_refresh_token(sub=sub),
    )


@auth_bp.get("/me", response_model=UserRead)
async def read_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return current_user


@auth_bp.post("/accept-disclaimer", response_model=UserRead)
async def accept_disclaimer(
    db: SessionDep, current_user: User = Depends(get_current_user)
):
    """Record that the current user accepted the medical-device disclaimer."""
    current_user.disclaimer_accepted_at = datetime.now(timezone.utc)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


# ── User Management (CRUD) ─────────────────────────────────────────────


def _require_role(*allowed_roles: str):
    """Return a dependency that checks the current user has one of ``allowed_roles``."""

    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' not allowed "
                f"(required: {', '.join(allowed_roles)})",
            )
        return current_user

    return _check


@auth_bp.get("/users", response_model=list[UserRead])
async def list_users(
    db: SessionDep,
    current_user: User = Depends(_require_role("admin", "demo_viewer")),
    offset: int = 0,
    limit: int = 100,
):
    """List users with pagination (admin or demo_viewer only)."""
    users = db.exec(select(User).offset(offset).limit(limit)).all()
    return users


@auth_bp.post("/users", response_model=UserRead, status_code=201)
async def create_user(
    user_in: UserCreate,
    db: SessionDep,
    current_user: User = Depends(_require_role("admin")),
):
    """Create a new user with role validation (admin only)."""
    existing = db.exec(select(User).where(User.name == user_in.name)).first()
    if existing:
        raise api_error(422, "user_exists", "User already exists")

    db_user = User(
        name=user_in.name,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role if user_in.role in ROLES else "user",
    )
    db.add(db_user)
    db.flush()
    audit(
        db,
        "user.create",
        actor=current_user,
        target_type="user",
        target_id=db_user.id,
        details={"name": db_user.name, "role": db_user.role},
    )
    db.commit()
    db.refresh(db_user)
    return db_user


@auth_bp.get("/users/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int,
    db: SessionDep,
    current_user: User = Depends(_require_role("admin", "demo_viewer")),
):
    """Return a single user by ID (admin or demo_viewer only)."""
    user = db.get(User, user_id)
    if not user:
        raise api_error(404, "user_not_found", "User not found")
    return user


@auth_bp.put("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: SessionDep,
    current_user: User = Depends(_require_role("admin")),
):
    """Update a user's name, active state, role, or password (admin only)."""
    user = db.get(User, user_id)
    if not user:
        raise api_error(404, "user_not_found", "User not found")

    before = {"name": user.name, "is_active": user.is_active, "role": user.role}
    if user_in.name is not None:
        user.name = user_in.name
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if user_in.role is not None and user_in.role in ROLES:
        user.role = user_in.role
    if user_in.password is not None:
        user.hashed_password = get_password_hash(user_in.password)

    after = {"name": user.name, "is_active": user.is_active, "role": user.role}
    details: dict = {"fields": changed_fields(before, after)}
    if user_in.password is not None:
        details["fields"].append("password")
    if before["role"] != after["role"]:
        details["role"] = {"from": before["role"], "to": after["role"]}
    if before["is_active"] != after["is_active"]:
        details["is_active"] = after["is_active"]
    audit(
        db,
        "user.update",
        actor=current_user,
        target_type="user",
        target_id=user.id,
        details=details,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@auth_bp.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: SessionDep,
    current_user: User = Depends(_require_role("admin")),
):
    """Delete a user by ID, preventing self-deletion (admin only)."""
    user = db.get(User, user_id)
    if not user:
        raise api_error(404, "user_not_found", "User not found")

    # Prevent self-deletion
    if user.id == current_user.id:
        raise api_error(400, "cannot_delete_self", "Cannot delete yourself")

    audit(
        db,
        "user.delete",
        actor=current_user,
        target_type="user",
        target_id=user.id,
        details={"name": user.name, "role": user.role},
    )
    db.delete(user)
    db.commit()
    return {"ok": True}
