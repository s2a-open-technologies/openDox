"""openDox - Medical transcription platform
Copyright (C) 2026  Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-FileCopyrightText: 2026 Christopher Abanilla <christopher.abanilla@gmx.de>
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

from fastapi import Request

from backend.components.modules.env import env_or_file


def request_base_url(request: Request) -> str:
    """Return the externally visible base URL of this server, incl. ROOT_PATH.

    Honours ``X-Forwarded-Proto`` and ``X-Forwarded-Host`` so it works behind a
    reverse proxy (Apache, nginx, Traefik) — but only when the immediate peer
    is a configured trusted proxy (``request.state.trusted_proxy``, set by
    ``run.py``'s ``mark_trusted_proxy`` middleware from ``TRUSTED_PROXY_IPS``).
    Otherwise these headers are attacker-controllable.

    Returns:
        URL without trailing slash, e.g. ``https://opendox.example.com/opendox``.
    """
    if getattr(request.state, "trusted_proxy", False):
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get(
            "x-forwarded-host", request.headers.get("host", request.url.netloc)
        )
    else:
        proto = request.url.scheme
        host = request.headers.get("host", request.url.netloc)
    root_path = (env_or_file("ROOT_PATH", "") or "").rstrip("/")
    return f"{proto}://{host}{root_path}"
