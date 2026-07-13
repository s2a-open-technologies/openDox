"""Tests for backend.components.services.sanitizing_service."""

import logging

import pytest
import requests

from backend.components.services.sanitizing_service import (
    _extract_mapping,
    reinject,
    sanitize,
)


def test_extract_mapping_simple_replace():
    original = "Herr Michael Müller kam"
    sanitized = "Herr [PERSON] kam"

    assert _extract_mapping(original, sanitized) == {"[PERSON]": "Michael Müller"}


def test_extract_mapping_no_differences_returns_empty():
    text = "Nothing changed here"

    assert _extract_mapping(text, text) == {}


def test_extract_mapping_skips_ambiguous_multi_token_block(caplog):
    # No separating text between the two entities on either side, so the
    # diff collapses both replacements into a single ambiguous block.
    original = "Herr Michael Müller Frau Anna Schmidt kam"
    sanitized = "Herr [PERSON] [PERSON] kam"

    with caplog.at_level(logging.WARNING):
        mapping = _extract_mapping(original, sanitized)

    assert mapping == {}
    assert "ambiguous" in caplog.text.lower()


def test_extract_mapping_strips_trailing_punctuation():
    original = "Er heißt Michael Müller."
    sanitized = "Er heißt [PERSON]."

    mapping = _extract_mapping(original, sanitized)

    assert mapping == {"[PERSON]": "Michael Müller"}


class _FakeResponse:
    def __init__(self, json_body, raise_error: bool = False):
        self._json_body = json_body
        self._raise_error = raise_error
        self.status_code = 500 if raise_error else 200

    def raise_for_status(self):
        if self._raise_error:
            raise requests.HTTPError("boom")

    def json(self):
        return self._json_body


def test_sanitize_uses_backend_mapping_when_provided(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["headers"] = headers
        return _FakeResponse(
            {
                "sanitized_text": "Herr [PERSON] kam",
                "mapping": {"[PERSON]": "Sentinel Value"},
            }
        )

    monkeypatch.setattr(requests, "post", fake_post)

    sanitized, mapping = sanitize(
        "Herr Michael Müller kam", "http://sanitizer/api", None
    )

    assert sanitized == "Herr [PERSON] kam"
    # The diff-based fallback would never produce this value — proves the
    # backend-provided mapping was used as-is, not recomputed.
    assert mapping == {"[PERSON]": "Sentinel Value"}


def test_sanitize_falls_back_to_diff_when_no_mapping_returned(monkeypatch):
    def fake_post(url, json, headers, timeout):
        return _FakeResponse({"sanitized_text": "Herr [PERSON] kam"})

    monkeypatch.setattr(requests, "post", fake_post)

    sanitized, mapping = sanitize(
        "Herr Michael Müller kam", "http://sanitizer/api", None
    )

    assert sanitized == "Herr [PERSON] kam"
    assert mapping == {"[PERSON]": "Michael Müller"}


def test_sanitize_propagates_http_error(monkeypatch):
    def fake_post(url, json, headers, timeout):
        return _FakeResponse({}, raise_error=True)

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(requests.HTTPError):
        sanitize("some text", "http://sanitizer/api", None)


def test_sanitize_sets_authorization_header_when_api_key_given(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["headers"] = headers
        return _FakeResponse({"sanitized_text": "x", "mapping": {}})

    monkeypatch.setattr(requests, "post", fake_post)

    sanitize("text", "http://sanitizer/api", "my-api-key")

    assert captured["headers"] == {"Authorization": "Bearer my-api-key"}


def test_sanitize_omits_authorization_header_when_no_api_key(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["headers"] = headers
        return _FakeResponse({"sanitized_text": "x", "mapping": {}})

    monkeypatch.setattr(requests, "post", fake_post)

    sanitize("text", "http://sanitizer/api", None)

    assert captured["headers"] == {}


def test_reinject_replaces_multiple_placeholders():
    text = "Hallo [PERSON], willkommen in [LOCATION]"
    mapping = {"[PERSON]": "Dr. Müller", "[LOCATION]": "Berlin"}

    result = reinject(text, mapping)

    assert result == "Hallo Dr. Müller, willkommen in Berlin"


def test_reinject_ignores_mapping_keys_not_present_in_text():
    text = "Hallo [PERSON]"
    mapping = {"[PERSON]": "Dr. Müller", "[LOCATION]": "Berlin"}

    result = reinject(text, mapping)

    assert result == "Hallo Dr. Müller"
