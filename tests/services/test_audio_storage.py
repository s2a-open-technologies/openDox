"""Tests for backend.components.services.audio_storage.

Mocks the boto3 S3 client so no real S3-compatible server is needed.
"""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from backend.components.services import audio_storage


@pytest.fixture
def patched_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(audio_storage, "_client", client)
    monkeypatch.setattr(audio_storage, "S3_BUCKET", "test-bucket")
    return client


def test_upload_bytes_calls_put_object(patched_client):
    audio_storage.upload_bytes("records/1.mp3.enc", b"encrypted-bytes")

    patched_client.put_object.assert_called_once_with(
        Bucket="test-bucket", Key="records/1.mp3.enc", Body=b"encrypted-bytes"
    )


def test_upload_bytes_raises_when_unconfigured(monkeypatch):
    monkeypatch.setattr(audio_storage, "_client", None)
    with pytest.raises(RuntimeError):
        audio_storage.upload_bytes("records/1.mp3.enc", b"data")


def test_download_bytes_returns_body(patched_client):
    patched_client.get_object.return_value = {
        "Body": MagicMock(read=MagicMock(return_value=b"encrypted-bytes"))
    }

    result = audio_storage.download_bytes("records/1.mp3.enc")

    assert result == b"encrypted-bytes"
    patched_client.get_object.assert_called_once_with(
        Bucket="test-bucket", Key="records/1.mp3.enc"
    )


def test_download_bytes_returns_none_for_missing_key(patched_client):
    patched_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "not found"}}, "GetObject"
    )

    assert audio_storage.download_bytes("records/missing.mp3.enc") is None


def test_download_bytes_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(audio_storage, "_client", None)
    assert audio_storage.download_bytes("records/1.mp3.enc") is None


def test_delete_calls_delete_object(patched_client):
    audio_storage.delete("records/1.mp3.enc")

    patched_client.delete_object.assert_called_once_with(
        Bucket="test-bucket", Key="records/1.mp3.enc"
    )


def test_delete_ignores_missing_key_errors(patched_client):
    patched_client.delete_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "not found"}}, "DeleteObject"
    )

    audio_storage.delete("records/missing.mp3.enc")  # must not raise
