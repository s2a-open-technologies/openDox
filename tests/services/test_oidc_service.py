"""Tests for backend.components.services.oidc.OidcService.

HTTP calls (discovery, token exchange, userinfo, JWKS) are monkeypatched at
the httpx.get/httpx.post level. verify_id_token() is exercised against a
real RS256-signed JWT and its matching public JWKS (generated on the fly),
so the signature-verification path is genuinely covered, not just mocked
away.
"""

import base64
import hashlib
import hmac
import json
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.components.services.oidc import OidcDiscoveryError, OidcService

DISCOVERY_DOC = {
    "authorization_endpoint": "https://provider.example.com/auth",
    "token_endpoint": "https://provider.example.com/token",
    "userinfo_endpoint": "https://provider.example.com/userinfo",
    "jwks_uri": "https://provider.example.com/jwks",
}


def _settings(**overrides):
    defaults = dict(
        provider_url="https://provider.example.com",
        client_id="my-client",
        client_secret="my-secret",
        scopes="openid email profile",
        group_claim="groups",
        allowed_groups="",
        admin_groups="",
        moderator_groups="",
        username_claim="preferred_username",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class _FakeResponse:
    def __init__(self, json_body, status_code=200):
        self._json_body = json_body
        self.status_code = status_code
        self.text = str(json_body)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json_body


@pytest.fixture
def discovery_get(monkeypatch):
    """Patch httpx.get to serve the discovery doc, recording other calls."""
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append({"url": url, "headers": headers})
        if url == "https://provider.example.com/.well-known/openid-configuration":
            return _FakeResponse(DISCOVERY_DOC)
        raise AssertionError(f"Unexpected GET {url}")

    monkeypatch.setattr(httpx, "get", fake_get)
    return calls


def test_discover_fetches_and_caches(discovery_get):
    service = OidcService(_settings())

    doc1 = service.discover()
    doc2 = service.discover()

    assert doc1 == DISCOVERY_DOC
    assert doc2 == DISCOVERY_DOC
    assert len(discovery_get) == 1  # second call served from cache


def test_discover_raises_on_missing_required_key(monkeypatch):
    incomplete_doc = {"authorization_endpoint": "x"}
    monkeypatch.setattr(
        httpx, "get", lambda url, timeout=None: _FakeResponse(incomplete_doc)
    )

    with pytest.raises(OidcDiscoveryError, match="missing"):
        OidcService(_settings()).discover()


def test_discover_raises_on_http_error(monkeypatch):
    def fake_get(url, timeout=None):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "get", fake_get)

    with pytest.raises(OidcDiscoveryError):
        OidcService(_settings()).discover()


def test_authorization_url_includes_expected_params(discovery_get):
    service = OidcService(_settings())

    url = service.authorization_url("https://app.example.com/callback", "state123")

    assert url.startswith("https://provider.example.com/auth?")
    assert "client_id=my-client" in url
    assert "redirect_uri=https://app.example.com/callback" in url
    assert "scope=openid email profile" in url
    assert "state=state123" in url


def test_exchange_code_posts_expected_data_and_returns_json(monkeypatch, discovery_get):
    captured = {}

    def fake_post(url, data=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        return _FakeResponse({"access_token": "at", "id_token": "it"})

    monkeypatch.setattr(httpx, "post", fake_post)

    result = OidcService(_settings()).exchange_code("auth-code", "https://app/callback")

    assert result == {"access_token": "at", "id_token": "it"}
    assert captured["url"] == "https://provider.example.com/token"
    assert captured["data"] == {
        "grant_type": "authorization_code",
        "code": "auth-code",
        "redirect_uri": "https://app/callback",
        "client_id": "my-client",
        "client_secret": "my-secret",
    }


def test_exchange_code_raises_on_non_200(monkeypatch, discovery_get):
    monkeypatch.setattr(
        httpx, "post", lambda url, data=None, timeout=None: _FakeResponse({}, 400)
    )

    with pytest.raises(OidcDiscoveryError):
        OidcService(_settings()).exchange_code("bad-code", "https://app/callback")


def test_get_userinfo_sends_bearer_token(monkeypatch, discovery_get):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        if url == DISCOVERY_DOC["userinfo_endpoint"]:
            captured["headers"] = headers
            return _FakeResponse({"preferred_username": "jdoe"})
        return _FakeResponse(DISCOVERY_DOC)

    monkeypatch.setattr(httpx, "get", fake_get)

    result = OidcService(_settings()).get_userinfo("my-access-token")

    assert result == {"preferred_username": "jdoe"}
    assert captured["headers"] == {"Authorization": "Bearer my-access-token"}


def test_get_userinfo_raises_on_non_200(monkeypatch, discovery_get):
    def fake_get(url, headers=None, timeout=None):
        if url == DISCOVERY_DOC["userinfo_endpoint"]:
            return _FakeResponse({}, 403)
        return _FakeResponse(DISCOVERY_DOC)

    monkeypatch.setattr(httpx, "get", fake_get)

    with pytest.raises(OidcDiscoveryError):
        OidcService(_settings()).get_userinfo("bad-token")


@pytest.fixture
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_jwk = json.loads(
        jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key())
    )
    public_jwk["kid"] = "test-kid"
    return SimpleNamespace(private_pem=private_pem, public_jwk=public_jwk)


def test_verify_id_token_accepts_correctly_signed_token(
    monkeypatch, discovery_get, rsa_keypair
):
    def fake_get(url, headers=None, timeout=None):
        if url == DISCOVERY_DOC["jwks_uri"]:
            return _FakeResponse({"keys": [rsa_keypair.public_jwk]})
        return _FakeResponse(DISCOVERY_DOC)

    monkeypatch.setattr(httpx, "get", fake_get)

    id_token = jwt.encode(
        {"sub": "42", "aud": "my-client", "preferred_username": "jdoe"},
        rsa_keypair.private_pem,
        algorithm="RS256",
        headers={"kid": "test-kid"},
    )

    claims = OidcService(_settings()).verify_id_token(id_token)

    assert claims["sub"] == "42"
    assert claims["preferred_username"] == "jdoe"


def test_verify_id_token_rejects_unknown_kid(monkeypatch, discovery_get, rsa_keypair):
    def fake_get(url, headers=None, timeout=None):
        if url == DISCOVERY_DOC["jwks_uri"]:
            return _FakeResponse({"keys": [rsa_keypair.public_jwk]})
        return _FakeResponse(DISCOVERY_DOC)

    monkeypatch.setattr(httpx, "get", fake_get)

    id_token = jwt.encode(
        {"sub": "42", "aud": "my-client"},
        rsa_keypair.private_pem,
        algorithm="RS256",
        headers={"kid": "some-other-kid"},
    )

    with pytest.raises(OidcDiscoveryError, match="No JWKS key"):
        OidcService(_settings()).verify_id_token(id_token)


def test_verify_id_token_rejects_wrong_audience(
    monkeypatch, discovery_get, rsa_keypair
):
    def fake_get(url, headers=None, timeout=None):
        if url == DISCOVERY_DOC["jwks_uri"]:
            return _FakeResponse({"keys": [rsa_keypair.public_jwk]})
        return _FakeResponse(DISCOVERY_DOC)

    monkeypatch.setattr(httpx, "get", fake_get)

    id_token = jwt.encode(
        {"sub": "42", "aud": "someone-elses-client"},
        rsa_keypair.private_pem,
        algorithm="RS256",
        headers={"kid": "test-kid"},
    )

    with pytest.raises(jwt.InvalidAudienceError):
        OidcService(_settings()).verify_id_token(id_token)


def test_verify_id_token_rejects_hs256_signed_with_public_key(
    monkeypatch, discovery_get, rsa_keypair
):
    """Algorithm confusion: an HS256 token keyed with the public JWK must fail."""

    def fake_get(url, headers=None, timeout=None):
        if url == DISCOVERY_DOC["jwks_uri"]:
            return _FakeResponse({"keys": [rsa_keypair.public_jwk]})
        return _FakeResponse(DISCOVERY_DOC)

    monkeypatch.setattr(httpx, "get", fake_get)

    def b64(raw: bytes) -> bytes:
        return base64.urlsafe_b64encode(raw).rstrip(b"=")

    signing_input = (
        b64(json.dumps({"alg": "HS256", "kid": "test-kid"}).encode())
        + b"."
        + b64(json.dumps({"sub": "42", "aud": "my-client"}).encode())
    )
    signature = hmac.new(
        json.dumps(rsa_keypair.public_jwk).encode(), signing_input, hashlib.sha256
    ).digest()
    id_token = (signing_input + b"." + b64(signature)).decode()

    with pytest.raises(jwt.PyJWTError):
        OidcService(_settings()).verify_id_token(id_token)


def test_map_groups_to_role_admin_takes_precedence_over_moderator():
    service = OidcService(
        _settings(admin_groups="admins", moderator_groups="mods, admins")
    )

    role = service.map_groups_to_role({"groups": ["admins"]})

    assert role == "admin"


def test_map_groups_to_role_moderator_when_no_admin_match():
    service = OidcService(_settings(admin_groups="admins", moderator_groups="mods"))

    role = service.map_groups_to_role({"groups": ["mods"]})

    assert role == "moderator"


def test_map_groups_to_role_defaults_to_user_without_group_match():
    service = OidcService(_settings(admin_groups="admins", moderator_groups="mods"))

    role = service.map_groups_to_role({"groups": ["everyone"]})

    assert role == "user"


def test_map_groups_to_role_handles_comma_separated_string_claim():
    service = OidcService(_settings(admin_groups="admins"))

    role = service.map_groups_to_role({"groups": "admins, staff"})

    assert role == "admin"


def test_map_groups_to_role_uses_custom_group_claim():
    service = OidcService(_settings(group_claim="roles", admin_groups="admins"))

    role = service.map_groups_to_role({"roles": ["admins"]})

    assert role == "admin"


def test_resolve_username_uses_default_claim():
    service = OidcService(_settings())

    assert service.resolve_username({"preferred_username": "jdoe"}) == "jdoe"


def test_resolve_username_returns_none_when_claim_missing():
    service = OidcService(_settings())

    assert service.resolve_username({}) is None


def test_resolve_username_uses_custom_claim():
    service = OidcService(_settings(username_claim="email"))

    assert service.resolve_username({"email": "jdoe@example.com"}) == "jdoe@example.com"


def test_is_authorized_requires_permitted_group():
    service = OidcService(_settings(allowed_groups="users", admin_groups="admins"))

    assert service.is_authorized({"groups": ["users"]}) is True
    assert service.is_authorized({"groups": ["admins"]}) is True
    assert service.is_authorized({"groups": ["other"]}) is False
    assert service.is_authorized({}) is False


def test_is_authorized_denies_everyone_without_configured_groups():
    service = OidcService(_settings())

    assert service.is_authorized({"groups": ["users"]}) is False
