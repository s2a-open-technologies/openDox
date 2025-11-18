# routers/auth.py
from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import select

from app.views.auth_api import auth_bp
from app.components.sql.sql_engine import SessionDep
from app.components.models.user_model import User, UserCreate, UserRead, UserLogin
from app.components.models.token_model import Token
from app.views.auth_api.dependencies import get_current_user
from app.components.security.hashing import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


@auth_bp.post("/register", response_model=UserRead, status_code=201)
async def register(user_in: UserCreate, db: SessionDep):
    
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
async def login(user_in: UserLogin, db: SessionDep):
    
    # Check if user exists and password is correct
    stmt = select(User).where(User.name == user_in.name)
    user = db.exec(stmt).first()

    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect name or password",
        )

    access_token = create_access_token(sub=str(user.id))
    refresh_token = create_refresh_token(sub=str(user.id))

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@auth_bp.post("/refresh", response_model=Token)
async def refresh_token_endpoint(refresh_token: str):
    
    # Refreshes token
    try:
        payload = decode_token(refresh_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
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
    return current_user
