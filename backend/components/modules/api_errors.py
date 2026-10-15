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

"""Machine-readable API errors the frontend can translate.

The frontend shows errors in the user's UI language, so user-facing errors
carry a stable code (looked up under errors.<code> in
frontend/src/i18n/locales/*/errors.json) next to a human-readable
message fallback and optional interpolation params.
"""

from typing import Any

from fastapi import HTTPException


def api_error(
    status_code: int, code: str, message: str, **params: Any
) -> HTTPException:
    """Build an HTTPException with a translatable detail payload.

    Args:
        status_code: HTTP status code.
        code: Stable snake_case error code, also the frontend translation key.
        message: Fallback text for API clients that do not translate code.
        **params: Values interpolated into the translated message.

    Returns:
        HTTPException whose detail is {"code", "message", "params"}.
    """
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "params": params},
    )
