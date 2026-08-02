"""Tests for backend.components.security.field_encryption."""

from cryptography.fernet import Fernet

from backend.components.security import field_encryption


def test_get_current_key_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(field_encryption, "_raw_key", None)
    monkeypatch.setattr(field_encryption, "_fernet", None)
    assert field_encryption.get_current_key() is None


def test_get_current_key_returns_bytes_when_configured(monkeypatch):
    monkeypatch.setattr(field_encryption, "_raw_key", "a-fake-key-value")
    assert field_encryption.get_current_key() == b"a-fake-key-value"


def test_encrypt_bytes_round_trip(monkeypatch):
    monkeypatch.setattr(field_encryption, "_fernet", Fernet(Fernet.generate_key()))
    plaintext = b"binary audio bytes \x00\x01\xff"
    encrypted = field_encryption.encrypt_bytes(plaintext)
    assert encrypted != plaintext
    assert field_encryption.decrypt_bytes(encrypted) == plaintext


def test_encrypt_bytes_passthrough_when_disabled(monkeypatch):
    monkeypatch.setattr(field_encryption, "_fernet", None)
    data = b"unencrypted bytes"
    assert field_encryption.encrypt_bytes(data) == data
    assert field_encryption.decrypt_bytes(data) == data


def test_encrypt_bytes_passthrough_for_empty_input(monkeypatch):
    monkeypatch.setattr(field_encryption, "_fernet", Fernet(Fernet.generate_key()))
    assert field_encryption.encrypt_bytes(b"") == b""
    assert field_encryption.decrypt_bytes(b"") == b""
