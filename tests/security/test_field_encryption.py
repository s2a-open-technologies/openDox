"""Tests for backend.components.security.field_encryption."""

from backend.components.security import field_encryption


def test_get_current_key_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(field_encryption, "_raw_key", None)
    monkeypatch.setattr(field_encryption, "_fernet", None)
    assert field_encryption.get_current_key() is None


def test_get_current_key_returns_bytes_when_configured(monkeypatch):
    monkeypatch.setattr(field_encryption, "_raw_key", "a-fake-key-value")
    assert field_encryption.get_current_key() == b"a-fake-key-value"
