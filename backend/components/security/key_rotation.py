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
import logging
from typing import Callable

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text
from sqlmodel import Session, select

from backend.components.models.encryption_key_state import EncryptionKeyState

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


def _reencrypt_batch(
    session: Session, rows, old_fernet: Fernet, new_fernet: Fernet
) -> int:
    """Re-encrypt one page of rows already fetched from the DB.

    Args:
        session: Active DB session (same one the rows were read through).
        rows: Iterable of row mappings with ``id`` and the encrypted columns.
        old_fernet: Fernet bound to the previous key.
        new_fernet: Fernet bound to the current key.

    Returns:
        Number of rows that had at least one column re-encrypted.
    """
    updated = 0
    for row in rows:
        new_values = {}
        for col in _ENCRYPTED_COLUMNS:
            new_val = _migrate_value(row[col], old_fernet, new_fernet)
            if new_val is not None:
                new_values[col] = new_val
        if new_values:
            set_clause = ", ".join(f"{col} = :{col}" for col in new_values)
            new_values["id"] = row["id"]
            session.execute(
                text(f"UPDATE record SET {set_clause} WHERE id = :id"), new_values
            )
            updated += 1
    return updated


def _reencrypt_all_records(
    session_factory: Callable[[], Session], old_fernet: Fernet, new_fernet: Fernet
) -> int:
    """Page through the record table, re-encrypting under the new key.

    Bypasses the ORM's ``EncryptedString`` type decorator on purpose — reading
    through the ORM would auto-decrypt with the *new* key and silently return
    ciphertext-as-plaintext on failure, making already-migrated rows and rows
    still under the old key indistinguishable.

    Args:
        session_factory: Callable returning a new DB session.
        old_fernet: Fernet bound to the previous key.
        new_fernet: Fernet bound to the current key.

    Returns:
        A ``(total_seen, total_updated)`` tuple: how many rows exist in total,
        and how many of them had at least one column re-encrypted. A mismatch
        between the two (rows exist but none were updated) signals that
        ``old_fernet`` couldn't decrypt anything — almost certainly a wrong
        ``ENCRYPTION_KEY_PREVIOUS``.
    """
    total_seen = 0
    total_updated = 0
    offset = 0
    while True:
        with session_factory() as session:
            rows = (
                session.execute(
                    text(
                        "SELECT id, content, summarize, pii_mapping FROM record "
                        "ORDER BY id LIMIT :limit OFFSET :offset"
                    ),
                    {"limit": BATCH_SIZE, "offset": offset},
                )
                .mappings()
                .all()
            )
            if not rows:
                break
            total_seen += len(rows)
            total_updated += _reencrypt_batch(session, rows, old_fernet, new_fernet)
            session.commit()
        if len(rows) < BATCH_SIZE:
            break
        offset += BATCH_SIZE
    return total_seen, total_updated


def run_key_rotation_if_needed(
    session_factory: Callable[[], Session],
    logger: logging.Logger,
    current_key: bytes | None,
    previous_key_raw: str | None,
) -> None:
    """Detect an ENCRYPTION_KEY rotation and re-encrypt existing data if needed.

    Args:
        session_factory: Callable returning a new DB session.
        logger: Logger for startup diagnostics.
        current_key: Raw bytes of the currently active key, or ``None`` if
            encryption is disabled (in which case this is a no-op).
        previous_key_raw: The previous key (``ENCRYPTION_KEY_PREVIOUS``), or
            ``None`` if not supplied.
    """
    logger.info("run_key_rotation_if_needed: entered")
    if current_key is None:
        logger.info("run_key_rotation_if_needed: encryption disabled, skipping")
        return

    fp = fingerprint_key(current_key)

    logger.info("run_key_rotation_if_needed: opening session")
    with session_factory() as session:
        logger.info("run_key_rotation_if_needed: session opened")
        if session.get_bind().dialect.name == "postgresql":
            logger.info("run_key_rotation_if_needed: setting lock_timeout")
            session.execute(text("SET LOCAL lock_timeout = '10s'"))
        logger.info("run_key_rotation_if_needed: fetching encryption key state row")
        state = session.exec(select(EncryptionKeyState)).first()
        state_desc = "none, first run"
        if state is not None:
            state_desc = f"fingerprint={state.key_fingerprint}"
        logger.info("run_key_rotation_if_needed: state row fetched (%s)", state_desc)
        if state is None:
            logger.info("run_key_rotation_if_needed: storing baseline fingerprint")
            session.add(EncryptionKeyState(key_fingerprint=fp))
            session.commit()
            logger.info("run_key_rotation_if_needed: baseline fingerprint stored")
            return
        if state.key_fingerprint == fp:
            logger.info("run_key_rotation_if_needed: fingerprint unchanged, no-op")
            return
        state_id = state.id

    logger.info("run_key_rotation_if_needed: fingerprint changed, rotation needed")
    if not previous_key_raw:
        logger.warning(
            "ENCRYPTION_KEY changed but ENCRYPTION_KEY_PREVIOUS is not set — "
            "existing encrypted data will stay unreadable until the previous "
            "key is supplied for a one-time migration."
        )
        return

    try:
        old_fernet = Fernet(previous_key_raw.encode())
    except ValueError:
        logger.warning("ENCRYPTION_KEY_PREVIOUS is not a valid Fernet key.")
        return

    new_fernet = Fernet(current_key)
    logger.info("run_key_rotation_if_needed: starting batched re-encryption")
    seen, updated = _reencrypt_all_records(session_factory, old_fernet, new_fernet)
    logger.info(
        "run_key_rotation_if_needed: re-encryption pass done (seen=%d, updated=%d)",
        seen,
        updated,
    )

    if seen > 0 and updated == 0:
        logger.warning(
            "0 of %d records re-encrypted — ENCRYPTION_KEY_PREVIOUS is likely "
            "incorrect. Fingerprint left unchanged; rotation will retry on the "
            "next restart.",
            seen,
        )
        return

    with session_factory() as session:
        state = session.get(EncryptionKeyState, state_id)
        state.key_fingerprint = fp
        session.add(state)
        session.commit()

    logger.info("Encryption key rotation complete (%d records re-encrypted)", updated)
