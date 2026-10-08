"""Tests for backend.components.security.key_rotation."""

import logging

from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlmodel import SQLModel, select

from backend.components.models.encryption_key_state import EncryptionKeyState
from backend.components.models.ldap_model import LdapSettingsModel
from backend.components.models.oidc_model import OidcSettingsModel
from backend.components.models.user_model import User
from backend.components.security.field_encryption import EncryptedString
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


def test_first_run_logs_checkpoints_along_the_way(session_factory, caplog):
    # Regression guard: this path used to be completely silent, which made a
    # production hang on the first SELECT indistinguishable from any other
    # stall further down the startup sequence.
    test_logger = logging.getLogger("test")
    with caplog.at_level(logging.INFO):
        run_key_rotation_if_needed(session_factory, test_logger, KEY_A, None)

    assert "entered" in caplog.text
    assert "fetching encryption key state row" in caplog.text
    assert "storing baseline fingerprint" in caplog.text
    assert "baseline fingerprint stored" in caplog.text


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


def test_every_encrypted_column_is_covered_by_rotation():
    """A new EncryptedString column must be added to _ENCRYPTED_TABLES."""
    from backend.components.security.key_rotation import _ENCRYPTED_TABLES

    covered = {(t, c) for t, cols in _ENCRYPTED_TABLES for c in cols}
    in_models = {
        (table.name, column.name)
        for table in SQLModel.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, EncryptedString)
    }
    assert in_models == covered


def _overwrite(session_factory, table, column, row_id, value):
    with session_factory() as session:
        session.execute(
            text(f'UPDATE "{table}" SET "{column}" = :v WHERE id = :id'),
            {"v": value, "id": row_id},
        )
        session.commit()


def _read_raw(session_factory, table, column, row_id):
    with session_factory() as session:
        return session.execute(
            text(f'SELECT "{column}" FROM "{table}" WHERE id = :id'), {"id": row_id}
        ).scalar_one()


def test_rotation_covers_title_and_settings_and_user_columns(session_factory):
    old_fernet = Fernet(KEY_A)
    run_key_rotation_if_needed(session_factory, logging.getLogger("test"), KEY_A, None)
    insert_raw_record(
        session_factory,
        record_id=1,
        content=old_fernet.encrypt(b"c").decode(),
        summarize=old_fernet.encrypt(b"s").decode(),
    )
    with session_factory() as session:
        session.add(User(name="alice", hashed_password="x"))
        session.add(
            LdapSettingsModel(
                server_host="h",
                server_port=389,
                base_dn="d",
                user_dn="u",
                bind_user_dn="cn=x",
            )
        )
        session.add(OidcSettingsModel())
        session.commit()
    expected = {
        ("record", "title", 1): b"Titel",
        ("user", "personal_glossary", 1): "Wörterbuch".encode(),
        ("ldapsettingsmodel", "bind_user_password", 1): b"ldap-secret",
        ("oidcsettingsmodel", "client_secret", 1): b"oidc-secret",
    }
    for (table, column, row_id), plain in expected.items():
        _overwrite(
            session_factory, table, column, row_id, old_fernet.encrypt(plain).decode()
        )

    run_key_rotation_if_needed(
        session_factory, logging.getLogger("test"), KEY_B, KEY_A.decode()
    )

    new_fernet = Fernet(KEY_B)
    for (table, column, row_id), plain in expected.items():
        raw = _read_raw(session_factory, table, column, row_id)
        assert new_fernet.decrypt(raw.encode()) == plain, (table, column)
    assert _read_fingerprint(session_factory) == fingerprint_key(KEY_B)


def test_empty_tables_do_not_trigger_wrong_key_warning(session_factory, caplog):
    run_key_rotation_if_needed(session_factory, logging.getLogger("test"), KEY_A, None)
    with session_factory() as session:
        session.add(User(name="bob", hashed_password="x"))  # no personal_glossary
        session.commit()

    with caplog.at_level(logging.WARNING):
        run_key_rotation_if_needed(
            session_factory, logging.getLogger("test"), KEY_B, KEY_A.decode()
        )

    assert "likely incorrect" not in caplog.text
    assert _read_fingerprint(session_factory) == fingerprint_key(KEY_B)
