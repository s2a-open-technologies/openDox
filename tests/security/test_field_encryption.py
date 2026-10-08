"""Tests for backend.components.security.field_encryption."""

import pytest
from cryptography.fernet import Fernet

from backend.components.security import field_encryption


def test_get_current_key_returns_bytes_when_configured(monkeypatch):
    monkeypatch.setattr(field_encryption, "_raw_key", "a-fake-key-value")
    assert field_encryption.get_current_key() == b"a-fake-key-value"


def test_encrypt_bytes_round_trip(monkeypatch):
    monkeypatch.setattr(field_encryption, "_fernet", Fernet(Fernet.generate_key()))
    plaintext = b"binary audio bytes \x00\x01\xff"
    encrypted = field_encryption.encrypt_bytes(plaintext)
    assert encrypted != plaintext
    assert field_encryption.decrypt_bytes(encrypted) == plaintext


def test_encrypt_bytes_passthrough_for_empty_input(monkeypatch):
    monkeypatch.setattr(field_encryption, "_fernet", Fernet(Fernet.generate_key()))
    assert field_encryption.encrypt_bytes(b"") == b""
    assert field_encryption.decrypt_bytes(b"") == b""


def _load_with(monkeypatch, key):
    """Call ``_load_key()`` with ENCRYPTION_KEY set to ``key`` (None = unset)."""
    for var in ("ENCRYPTION_KEY", "ENCRYPTION_KEY_FILE"):
        monkeypatch.delenv(var, raising=False)
    if key is not None:
        monkeypatch.setenv("ENCRYPTION_KEY", key)
    return field_encryption._load_key()


@pytest.mark.parametrize("missing", [None, "", "   "])
def test_startup_refuses_missing_key(monkeypatch, missing):
    with pytest.raises(field_encryption.EncryptionKeyError):
        _load_with(monkeypatch, missing)


def test_startup_refuses_invalid_key(monkeypatch):
    with pytest.raises(field_encryption.EncryptionKeyError):
        _load_with(monkeypatch, "not-a-fernet-key")


def test_startup_accepts_valid_key(monkeypatch):
    key = Fernet.generate_key().decode()
    assert _load_with(monkeypatch, key) == key


def test_encrypt_never_returns_plaintext():
    assert field_encryption.encrypt("Patient") != "Patient"
    assert field_encryption.decrypt(field_encryption.encrypt("Patient")) == "Patient"
