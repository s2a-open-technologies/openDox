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

import hashlib
import logging
from typing import Callable

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text
from sqlmodel import Session, select

from backend.components.models.encryption_key_state import EncryptionKeyState

BATCH_SIZE = 500
# Every table with ``EncryptedString`` columns: (table, encrypted columns).
# Each table has an integer ``id`` primary key. Keep in sync with the models —
# a column missing here stays under the old key and becomes unreadable after a
# rotation (tests/security/test_key_rotation.py checks the list against the
# metadata).
_ENCRYPTED_TABLES = (
    ("record", ("title", "content", "summarize", "pii_mapping")),
    ("dictionary", ("terms",)),
    ("ldapsettingsmodel", ("bind_user_password",)),
    ("oidcsettingsmodel", ("client_secret",)),
    ("user", ("idp_refresh_token",)),
)


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
    session: Session,
    table: str,
    columns: tuple[str, ...],
    rows,
    old_fernet: Fernet,
    new_fernet: Fernet,
) -> tuple[int, int]:
    """Re-encrypt one page of rows already fetched from the DB.

    Args:
        session: Active DB session (same one the rows were read through).
        table: Table the rows belong to.
        columns: Encrypted columns of that table.
        rows: Iterable of row mappings with ``id`` and the encrypted columns.
        old_fernet: Fernet bound to the previous key.
        new_fernet: Fernet bound to the current key.

    Returns:
        A ``(seen, updated)`` tuple: rows holding at least one non-empty
        encrypted value, and how many of those had a column re-encrypted.
    """
    seen = 0
    updated = 0
    for row in rows:
        if not any(row[col] for col in columns):
            continue
        seen += 1
        new_values = {}
        for col in columns:
            new_val = _migrate_value(row[col], old_fernet, new_fernet)
            if new_val is not None:
                new_values[col] = new_val
        if new_values:
            set_clause = ", ".join(f'"{col}" = :{col}' for col in new_values)
            new_values["id"] = row["id"]
            session.execute(
                text(f'UPDATE "{table}" SET {set_clause} WHERE id = :id'), new_values
            )
            updated += 1
    return seen, updated


def _reencrypt_table(
    session_factory: Callable[[], Session],
    table: str,
    columns: tuple[str, ...],
    old_fernet: Fernet,
    new_fernet: Fernet,
) -> tuple[int, int]:
    """Page through one table, re-encrypting its encrypted columns.

    Bypasses the ORM's ``EncryptedString`` type decorator on purpose — reading
    through the ORM would auto-decrypt with the *new* key and silently return
    ciphertext-as-plaintext on failure, making already-migrated rows and rows
    still under the old key indistinguishable.

    Args:
        session_factory: Callable returning a new DB session.
        table: Table to process.
        columns: Encrypted columns of that table.
        old_fernet: Fernet bound to the previous key.
        new_fernet: Fernet bound to the current key.

    Returns:
        A ``(seen, updated)`` tuple, see ``_reencrypt_batch``.
    """
    col_list = ", ".join(f'"{col}"' for col in columns)
    total_seen = 0
    total_updated = 0
    offset = 0
    while True:
        with session_factory() as session:
            rows = (
                session.execute(
                    text(
                        f'SELECT id, {col_list} FROM "{table}" '
                        "ORDER BY id LIMIT :limit OFFSET :offset"
                    ),
                    {"limit": BATCH_SIZE, "offset": offset},
                )
                .mappings()
                .all()
            )
            if not rows:
                break
            seen, updated = _reencrypt_batch(
                session, table, columns, rows, old_fernet, new_fernet
            )
            total_seen += seen
            total_updated += updated
            session.commit()
        if len(rows) < BATCH_SIZE:
            break
        offset += BATCH_SIZE
    return total_seen, total_updated


def _reencrypt_all(
    session_factory: Callable[[], Session], old_fernet: Fernet, new_fernet: Fernet
) -> tuple[int, int]:
    """Re-encrypt every encrypted column in ``_ENCRYPTED_TABLES``.

    Returns:
        A ``(seen, updated)`` tuple summed over all tables. ``seen > 0`` with
        ``updated == 0`` signals that ``old_fernet`` couldn't decrypt anything —
        almost certainly a wrong ``ENCRYPTION_KEY_PREVIOUS``.
    """
    total_seen = 0
    total_updated = 0
    for table, columns in _ENCRYPTED_TABLES:
        seen, updated = _reencrypt_table(
            session_factory, table, columns, old_fernet, new_fernet
        )
        total_seen += seen
        total_updated += updated
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
        current_key: Raw bytes of the currently active key (``None`` is only
            accepted for callers that have no key, and makes this a no-op).
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
    seen, updated = _reencrypt_all(session_factory, old_fernet, new_fernet)
    logger.info(
        "run_key_rotation_if_needed: re-encryption pass done (seen=%d, updated=%d)",
        seen,
        updated,
    )

    if seen > 0 and updated == 0:
        logger.warning(
            "0 of %d encrypted rows re-encrypted — ENCRYPTION_KEY_PREVIOUS is likely "
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

    logger.info("Encryption key rotation complete (%d rows re-encrypted)", updated)
