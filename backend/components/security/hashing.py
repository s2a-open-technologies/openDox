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

from datetime import datetime, timedelta, timezone
from typing import Union

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.components.modules.env import env_or_file

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = env_or_file("SECRET_KEY", "TestintDebugKey")
ALGORITHM = env_or_file("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = env_or_file("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
REFRESH_TOKEN_EXPIRE_DAYS = env_or_file("REFRESH_TOKEN_EXPIRE_DAYS", "7")


def get_password_hash(password):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def create_token(
    data: dict, expires_delta: Union[timedelta, None] = None, token_type: str = "access"
) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        if token_type == "refresh":
            expire = now + timedelta(days=int(REFRESH_TOKEN_EXPIRE_DAYS))
        else:
            expire = now + timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": now, "token_type": token_type})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_access_token(sub: str) -> str:
    """Create a short-lived access token for a user ID."""
    return create_token({"sub": sub}, token_type="access")


def create_refresh_token(sub: str) -> str:
    """Create a long-lived refresh token for a user ID."""
    return create_token({"sub": sub}, token_type="refresh")


def decode_token(token: str) -> Union[dict, None]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(payload)
        return payload
    except JWTError:
        return None
