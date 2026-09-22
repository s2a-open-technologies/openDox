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

import logging

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from backend.components.modules.env import env_or_file

logger = logging.getLogger(__name__)

_raw_key = env_or_file("ENCRYPTION_KEY", None)

if _raw_key is None:
    logger.warning(
        "ENCRYPTION_KEY is not set — patient data will be stored unencrypted. "
        "Set ENCRYPTION_KEY to a Fernet key for DSGVO compliance. "
        "Generate one with: "
        'python -c "from cryptography.fernet import Fernet; '
        'print(Fernet.generate_key().decode())"'
    )
    _fernet = None
else:
    _fernet = Fernet(_raw_key.encode() if isinstance(_raw_key, str) else _raw_key)


def get_current_key() -> bytes | None:
    """Return the raw ``ENCRYPTION_KEY`` bytes currently configured.

    Returns:
        The key as bytes, or ``None`` if ``ENCRYPTION_KEY`` is not set
        (encryption disabled).
    """
    if _raw_key is None:
        return None
    return _raw_key.encode() if isinstance(_raw_key, str) else _raw_key


def encrypt(value: str) -> str:
    """Encrypt a string with Fernet, returning plaintext if disabled."""
    if _fernet is None or not value:
        return value
    return _fernet.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Decrypt a Fernet-encrypted string.

    Falls back to plaintext for unencrypted legacy data.
    """
    if _fernet is None or not value:
        return value
    try:
        return _fernet.decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        # Old plaintext record — return as-is to allow gradual migration
        return value


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt raw bytes (e.g. audio) with the same key as ``encrypt``."""
    if _fernet is None or not data:
        return data
    return _fernet.encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    """Decrypt bytes produced by ``encrypt_bytes``."""
    if _fernet is None or not data:
        return data
    return _fernet.decrypt(data)


class EncryptedString(TypeDecorator):
    """SQLAlchemy column type that transparently encrypts on write.

    Decrypts on read.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Encrypt the value before it is written to the database."""
        if value is None:
            return value
        return encrypt(value)

    def process_result_value(self, value, dialect):
        """Decrypt the value after it is read from the database."""
        if value is None:
            return value
        return decrypt(value)
