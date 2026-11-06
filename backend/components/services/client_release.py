"""openDox - Medical transcription platform
Copyright (C) 2026  S2A Open Technologies gGmbH
SPDX-FileCopyrightText: 2026 S2A Open Technologies gGmbH
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

Newest published desktop-client version (for the client's "update available" hint).

The server asks GitHub instead of every client doing it, so workstations keep
talking to the openDox server only. Purely informational: the client shows a
note in its settings dialog, installing stays with the customer's IT.
``CLIENT_LATEST_RELEASE_URL=""`` turns the lookup off (e.g. offline networks).
"""

import time

import httpx

from backend.components.modules.env import env_or_file
from backend.components.modules.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_RELEASE_URL = (
    "https://api.github.com/repos/s2a-open-technologies/openDox-client/releases/latest"
)
_TIMEOUT_SECONDS = 5.0
_SUCCESS_TTL_SECONDS = 6 * 3600
_FAILURE_TTL_SECONDS = 15 * 60

# (version or None, expires_at monotonic) — module-level, per worker process.
_cache: tuple[str | None, float] | None = None


def _release_url() -> str:
    # env_or_file returns the default only when the variable is unset; an explicit
    # empty value means "disabled".
    return env_or_file("CLIENT_LATEST_RELEASE_URL", _DEFAULT_RELEASE_URL).strip()


async def _fetch(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(
                url, headers={"Accept": "application/vnd.github+json"}
            )
        response.raise_for_status()
        tag = str(response.json().get("tag_name") or "").strip()
    except Exception as exc:  # network, HTTP, JSON — never break client-config
        logger.info("Latest client version not available: %s", exc)
        return None
    version = tag[1:] if tag[:1] in ("v", "V") else tag
    return version or None


async def latest_client_version() -> str | None:
    """Return the newest client version (``"0.9.0"``) or ``None``; cached."""
    global _cache
    now = time.monotonic()
    if _cache is not None and now < _cache[1]:
        return _cache[0]
    url = _release_url()
    if not url:
        return None
    version = await _fetch(url)
    ttl = _SUCCESS_TTL_SECONDS if version else _FAILURE_TTL_SECONDS
    _cache = (version, now + ttl)
    return version


def reset_cache() -> None:
    """Forget the cached value (tests)."""
    global _cache
    _cache = None
