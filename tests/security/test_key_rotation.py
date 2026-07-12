"""Tests for backend.components.security.key_rotation."""

from cryptography.fernet import Fernet

from backend.components.security.key_rotation import _migrate_value, fingerprint_key

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
