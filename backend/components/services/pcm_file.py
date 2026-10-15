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


The raw PCM file of a recording session.
"""

import os

from backend.components.modules.logger import get_logger

logger = get_logger(__name__)

# Raw PCM is float32: every sample is 4 bytes.
_SAMPLE_BYTES = 4


def open_session_audio(path: str) -> int:
    """Create the PCM file of a new session, or adopt the one already on disk.

    A session is rebuilt from the database record when the session store lost it
    (server restart without Redis, Redis data gone). The audio recorded so far is
    still in the file, so it must be kept and appended to, not emptied. A crash
    can leave half a sample at the end; that is cut off, because the WAV
    conversion needs a multiple of 4 bytes.

    Returns:
        The number of audio bytes in the file (0 for a new recording).
    """
    if not os.path.exists(path):
        open(path, "wb").close()
        return 0
    size = os.path.getsize(path)
    whole = size - size % _SAMPLE_BYTES
    if whole != size:
        os.truncate(path, whole)
    if whole:
        logger.info(
            "Continuing recording with %d bytes of existing audio: %s", whole, path
        )
    return whole
