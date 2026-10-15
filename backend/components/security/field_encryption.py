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

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from backend.components.modules.env import env_or_file

logger = logging.getLogger(__name__)


class EncryptionKeyError(RuntimeError):
    """ENCRYPTION_KEY is missing or not a valid Fernet key."""


def _load_key() -> str:
    """Return ``ENCRYPTION_KEY``; refuse to run without a valid one.

    Patient data must never be stored in plaintext, so there is deliberately no
    "encryption disabled" mode: the application does not start without a key.

    Raises:
        EncryptionKeyError: If the key is unset, empty or not a Fernet key.
    """
    raw = (env_or_file("ENCRYPTION_KEY", None) or "").strip()
    if not raw:
        logger.critical(
            "ENCRYPTION_KEY is not set. openDox refuses to start without it, "
            "because patient data must not be stored unencrypted. Generate one "
            'with: python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())" and set ENCRYPTION_KEY '
            "(or ENCRYPTION_KEY_FILE)."
        )
        raise EncryptionKeyError("ENCRYPTION_KEY is required but not set")
    try:
        Fernet(raw.encode())
    except ValueError as exc:
        logger.critical("ENCRYPTION_KEY is not a valid Fernet key: %s", exc)
        raise EncryptionKeyError("ENCRYPTION_KEY is not a valid Fernet key") from exc
    return raw


_raw_key = _load_key()
_fernet = Fernet(_raw_key.encode())


def get_current_key() -> bytes:
    """Return the raw ``ENCRYPTION_KEY`` bytes currently configured."""
    return _raw_key.encode() if isinstance(_raw_key, str) else _raw_key


def encrypt(value: str) -> str:
    """Encrypt a string with Fernet (empty values stay empty)."""
    if not value:
        return value
    return _fernet.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Decrypt a Fernet-encrypted string.

    Falls back to plaintext for unencrypted legacy data.
    """
    if not value:
        return value
    try:
        return _fernet.decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        # Old plaintext record — return as-is to allow gradual migration
        return value


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt raw bytes (e.g. audio) with the same key as ``encrypt``."""
    if not data:
        return data
    return _fernet.encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    """Decrypt bytes produced by ``encrypt_bytes``."""
    if not data:
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
