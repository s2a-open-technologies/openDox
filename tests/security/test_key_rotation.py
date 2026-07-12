"""Tests for backend.components.security.key_rotation."""

import logging

from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlmodel import select

from backend.components.models.encryption_key_state import EncryptionKeyState
from backend.components.security.key_rotation import (
    _migrate_value,
    fingerprint_key,
    run_key_rotation_if_needed,
)
from tests.security.conftest import insert_raw_record

KEY_A = Fernet.generate_key()
KEY_B = Fernet.generate_key()


def test_fingerprint_key_is_deterministic():
    assert fingerprint_key(KEY_A) == fingerprint_key(KEY_A)


def test_fingerprint_key_differs_per_key():
    assert fingerprint_key(KEY_A) != fingerprint_key(KEY_B)


def test_migrate_value_reencrypts_value_under_old_key():
    old_fernet = Fernet(KEY_A)
    new_fernet = Fernet(KEY_B)
    raw = old_fernet.encrypt(b"hello world").decode()

    result = _migrate_value(raw, old_fernet, new_fernet)

    assert result is not None
    assert new_fernet.decrypt(result.encode()) == b"hello world"


def test_migrate_value_skips_value_already_under_new_key():
    old_fernet = Fernet(KEY_A)
    new_fernet = Fernet(KEY_B)
    raw = new_fernet.encrypt(b"already migrated").decode()

    assert _migrate_value(raw, old_fernet, new_fernet) is None


def test_migrate_value_skips_legacy_plaintext():
    old_fernet = Fernet(KEY_A)
    new_fernet = Fernet(KEY_B)

    assert (
        _migrate_value("just plain text, never encrypted", old_fernet, new_fernet)
        is None
    )


def test_migrate_value_skips_empty_and_none():
    old_fernet = Fernet(KEY_A)
    new_fernet = Fernet(KEY_B)

    assert _migrate_value("", old_fernet, new_fernet) is None
    assert _migrate_value(None, old_fernet, new_fernet) is None


def _read_record_content(session_factory, record_id: int) -> str:
    with session_factory() as session:
        row = (
            session.execute(
                text("SELECT content FROM record WHERE id = :id"), {"id": record_id}
            )
            .mappings()
            .one()
        )
        return row["content"]


def _read_fingerprint(session_factory) -> str | None:
    with session_factory() as session:
        state = session.exec(select(EncryptionKeyState)).first()
        return state.key_fingerprint if state else None


def test_first_run_stores_baseline_without_migrating(session_factory):
    run_key_rotation_if_needed(session_factory, logging.getLogger("test"), KEY_A, None)

    assert _read_fingerprint(session_factory) == fingerprint_key(KEY_A)


def test_no_rotation_when_fingerprint_matches(session_factory):
    run_key_rotation_if_needed(session_factory, logging.getLogger("test"), KEY_A, None)
    # Second call with the same key must be a no-op fast path.
    run_key_rotation_if_needed(session_factory, logging.getLogger("test"), KEY_A, None)

    assert _read_fingerprint(session_factory) == fingerprint_key(KEY_A)


def test_rotation_reencrypts_records_and_updates_fingerprint(session_factory):
    old_fernet = Fernet(KEY_A)
    run_key_rotation_if_needed(session_factory, logging.getLogger("test"), KEY_A, None)
    insert_raw_record(
        session_factory,
        record_id=1,
        content=old_fernet.encrypt(b"patient note").decode(),
        summarize=old_fernet.encrypt(b"summary").decode(),
    )

    run_key_rotation_if_needed(
        session_factory, logging.getLogger("test"), KEY_B, KEY_A.decode()
    )

    new_fernet = Fernet(KEY_B)
    migrated = _read_record_content(session_factory, 1)
    assert new_fernet.decrypt(migrated.encode()) == b"patient note"
    assert _read_fingerprint(session_factory) == fingerprint_key(KEY_B)


def test_missing_previous_key_leaves_fingerprint_unchanged(session_factory, caplog):
    run_key_rotation_if_needed(session_factory, logging.getLogger("test"), KEY_A, None)

    with caplog.at_level(logging.WARNING):
        run_key_rotation_if_needed(
            session_factory, logging.getLogger("test"), KEY_B, None
        )

    assert _read_fingerprint(session_factory) == fingerprint_key(KEY_A)
    assert "ENCRYPTION_KEY_PREVIOUS" in caplog.text


def test_wrong_previous_key_migrates_nothing(session_factory):
    old_fernet = Fernet(KEY_A)
    wrong_key = Fernet.generate_key()
    original_content = old_fernet.encrypt(b"patient note").decode()
    run_key_rotation_if_needed(session_factory, logging.getLogger("test"), KEY_A, None)
    insert_raw_record(
        session_factory,
        record_id=1,
        content=original_content,
        summarize=old_fernet.encrypt(b"summary").decode(),
    )

    run_key_rotation_if_needed(
        session_factory, logging.getLogger("test"), KEY_B, wrong_key.decode()
    )

    unchanged = _read_record_content(session_factory, 1)
    assert unchanged == original_content
    assert _read_fingerprint(session_factory) == fingerprint_key(KEY_A)


def test_rerun_after_successful_rotation_is_a_noop(session_factory):
    old_fernet = Fernet(KEY_A)
    run_key_rotation_if_needed(session_factory, logging.getLogger("test"), KEY_A, None)
    insert_raw_record(
        session_factory,
        record_id=1,
        content=old_fernet.encrypt(b"patient note").decode(),
        summarize=old_fernet.encrypt(b"summary").decode(),
    )
    run_key_rotation_if_needed(
        session_factory, logging.getLogger("test"), KEY_B, KEY_A.decode()
    )

    # Same keys again: fingerprint already matches KEY_B, must be a no-op.
    run_key_rotation_if_needed(
        session_factory, logging.getLogger("test"), KEY_B, KEY_A.decode()
    )

    new_fernet = Fernet(KEY_B)
    migrated = _read_record_content(session_factory, 1)
    assert new_fernet.decrypt(migrated.encode()) == b"patient note"
