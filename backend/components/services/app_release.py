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

Newest published openDox release (for the admin "update available" banner).

The server asks GitHub once per cache period, the browser only talks to the
openDox server. Purely informational: installing stays with the operator.
``OPENDOX_LATEST_RELEASE_URL=""`` turns the lookup off (e.g. offline networks).
"""

import re
import time

import httpx

from backend.components.modules.env import env_or_file
from backend.components.modules.logger import get_logger

logger = get_logger(__name__)

REPO_RELEASES_URL = "https://github.com/s2a-open-technologies/openDox/releases"
_DEFAULT_RELEASE_URL = (
    "https://api.github.com/repos/s2a-open-technologies/openDox/releases/latest"
)
_TIMEOUT_SECONDS = 5.0
_SUCCESS_TTL_SECONDS = 6 * 3600
_FAILURE_TTL_SECONDS = 15 * 60

# (version or None, expires_at monotonic) — module-level, per worker process.
_cache: tuple[str | None, float] | None = None


def _release_url() -> str:
    # An explicit empty value means "disabled"; unset falls back to GitHub.
    return env_or_file("OPENDOX_LATEST_RELEASE_URL", _DEFAULT_RELEASE_URL).strip()


def parse_version(value: str) -> tuple[int, ...] | None:
    """Parse ``"0.12.1"`` / ``"v0.12.1"`` into ``(0, 12, 1)``; ``None`` if unusable."""
    match = re.match(r"^[vV]?(\d+(?:\.\d+)*)", (value or "").strip())
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def is_newer(latest: str, current: str) -> bool:
    """Return True if ``latest`` is a higher version than ``current``."""
    a, b = parse_version(latest), parse_version(current)
    if a is None or b is None:
        return False
    size = max(len(a), len(b))
    return a + (0,) * (size - len(a)) > b + (0,) * (size - len(b))


async def _fetch(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(
                url, headers={"Accept": "application/vnd.github+json"}
            )
        response.raise_for_status()
        tag = str(response.json().get("tag_name") or "").strip()
    except Exception as exc:  # network, HTTP, JSON — never break the banner
        logger.info("Latest openDox version not available: %s", exc)
        return None
    version = tag[1:] if tag[:1] in ("v", "V") else tag
    return version or None


async def latest_version() -> str | None:
    """Return the newest openDox version (``"0.13.0"``) or ``None``; cached."""
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
