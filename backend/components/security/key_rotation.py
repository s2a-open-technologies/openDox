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

import hashlib

from cryptography.fernet import Fernet, InvalidToken

BATCH_SIZE = 500
_ENCRYPTED_COLUMNS = ("content", "summarize", "pii_mapping")


def fingerprint_key(key: bytes) -> str:
    """Return a SHA-256 hex digest identifying a Fernet key.

    Never persist or log the key itself — only this fingerprint.

    Args:
        key: Raw Fernet key bytes.

    Returns:
        Hex-encoded SHA-256 digest of the key.
    """
    return hashlib.sha256(key).hexdigest()


def _migrate_value(
    raw: str | None, old_fernet: Fernet, new_fernet: Fernet
) -> str | None:
    """Re-encrypt one column value from the old key to the new key.

    Args:
        raw: The current column value (ciphertext or legacy plaintext).
        old_fernet: Fernet bound to the previous key.
        new_fernet: Fernet bound to the current key.

    Returns:
        New ciphertext to write, or ``None`` if no update is needed —
        either the value already decrypts under the new key (already
        migrated) or it isn't decryptable with the old key either
        (legacy plaintext, left untouched).
    """
    if not raw:
        return None
    try:
        plaintext = old_fernet.decrypt(raw.encode())
    except (InvalidToken, Exception):
        return None
    return new_fernet.encrypt(plaintext).decode()
