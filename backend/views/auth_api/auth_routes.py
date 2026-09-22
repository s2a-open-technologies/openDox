"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-FileCopyrightText: 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
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
from datetime import datetime

from fastapi import Depends, HTTPException, Request, status
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
from backend.components.security.hashing import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from backend.components.services.ldap import LdapService
from backend.components.services.rate_limiter import login_limiter
from backend.components.sql.sql_engine import SessionDep
from backend.views.auth_api import auth_bp
from backend.views.auth_api.dependencies import get_current_user

# ── Authentication ──────────────────────────────────────────────────────


@auth_bp.post("/register", response_model=UserRead, status_code=201)
async def register(user_in: UserCreate, db: SessionDep):
    """Register a new user with a hashed password."""
    # check i user already exists
    stmt = select(User).where(User.name == user_in.name)
    existing_user = db.exec(stmt).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="User already exists",
        )

    # Create new user
    db_user = User(
        name=user_in.name,
        hashed_password=get_password_hash(user_in.password),
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@auth_bp.post("/login", response_model=Token)
async def login(request: Request, user_in: UserLogin, db: SessionDep):
    """Authenticate via local DB or LDAP and return a token pair."""
    login_limiter.check(request)

    # Check if user exists and password is correct
    stmt = select(User).where(User.name == user_in.name)
    user = db.exec(stmt).first()

    # 1. Local Login
    if user and user.hashed_password:
        if verify_password(user_in.password, user.hashed_password):
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
                )
                db.add(user)

            else:
                # Update existing user if needed (e.g. reactivate, re-sync role
                # from current LDAP group membership on every login)
                user.is_active = True
                user.role = role

            db.commit()
            db.refresh(user)

            access_token = create_access_token(sub=str(user.id))
            refresh_token = create_refresh_token(sub=str(user.id))
            return Token(access_token=access_token, refresh_token=refresh_token)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect name or password",
    )


@auth_bp.post("/refresh", response_model=Token)
async def refresh_token_endpoint(refresh_token: str):
    """Issue a new token pair for a valid refresh token."""
    # Refreshes token
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

    new_access = create_access_token(sub=sub)
    new_refresh = create_refresh_token(sub=sub)

    return Token(
        access_token=new_access,
        refresh_token=new_refresh,
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
    current_user.disclaimer_accepted_at = datetime.utcnow()
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
        raise HTTPException(status_code=422, detail="User already exists")

    db_user = User(
        name=user_in.name,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role if user_in.role in ROLES else "user",
    )
    db.add(db_user)
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
        raise HTTPException(status_code=404, detail="User not found")
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
        raise HTTPException(status_code=404, detail="User not found")

    if user_in.name is not None:
        user.name = user_in.name
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if user_in.role is not None and user_in.role in ROLES:
        user.role = user_in.role
    if user_in.password is not None:
        user.hashed_password = get_password_hash(user_in.password)

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
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    db.delete(user)
    db.commit()
    return {"ok": True}
