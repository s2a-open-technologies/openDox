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

import boto3
from botocore.exceptions import ClientError

from backend.components.modules.env import env_or_file
from backend.components.modules.logger import get_logger

logger = get_logger(__name__)

S3_ENDPOINT_URL = env_or_file("S3_ENDPOINT_URL", None)
S3_BUCKET = env_or_file("S3_BUCKET", None)
S3_ACCESS_KEY_ID = env_or_file("S3_ACCESS_KEY_ID", None)
S3_SECRET_ACCESS_KEY = env_or_file("S3_SECRET_ACCESS_KEY", None)
S3_REGION = env_or_file("S3_REGION", "garage")

_client = None
if S3_ENDPOINT_URL and S3_BUCKET:
    _client = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
        region_name=S3_REGION,
    )
else:
    logger.warning(
        "S3_ENDPOINT_URL/S3_BUCKET not set — persisted audio downloads are disabled."
    )


def is_configured() -> bool:
    """Return whether S3 storage is set up (client was built from env vars)."""
    return _client is not None


def head_bucket() -> None:
    """Probe the configured bucket. Raises if unreachable/misconfigured.

    Used by the admin "System" health check — a lightweight connectivity
    test that doesn't read/write any object.
    """
    _client.head_bucket(Bucket=S3_BUCKET)


def upload_bytes(key: str, data: bytes) -> None:
    """Upload bytes to the configured S3 bucket under ``key``."""
    if _client is None:
        raise RuntimeError("S3 storage is not configured")
    _client.put_object(Bucket=S3_BUCKET, Key=key, Body=data)


def download_bytes(key: str) -> bytes | None:
    """Download bytes stored under ``key``, or ``None`` if missing/unconfigured."""
    if _client is None or not key:
        return None
    try:
        response = _client.get_object(Bucket=S3_BUCKET, Key=key)
        return response["Body"].read()
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code in ("NoSuchKey", "404"):
            return None
        logger.warning(f"[S3] Failed to download key {key}: {e}")
        return None


def delete(key: str) -> None:
    """Delete the object stored under ``key``, ignoring missing-key errors."""
    if _client is None or not key:
        return
    try:
        _client.delete_object(Bucket=S3_BUCKET, Key=key)
    except ClientError as e:
        logger.warning(f"[S3] Failed to delete key {key}: {e}")
