"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-FileCopyrightText: 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
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


Delete recordings left in ``chunks/`` that no instance is working on.

``chunks/`` may be shared by several app instances (replicas on one node mount
the same volume). Deleting "everything" at startup, as a single instance may
do, would wipe other instances' live recordings. A file is therefore only
removed if it is old (nobody has written to it lately) and not referenced by a
session in the session store (a paused recording is old but resumable).
"""

import os
import time

from backend.components.modules.logger import get_logger

logger = get_logger(__name__)


def cleanup_orphaned_chunk_files(
    chunks_dir: str, active_paths: set[str], min_age_s: float
) -> int:
    """Remove ``session_*.pcm`` / ``session_*.wav`` that are old and unreferenced.

    Args:
        chunks_dir: Directory to scan (top level only, so ``failed/`` is safe).
        active_paths: Absolute paths of PCM files that belong to known sessions.
        min_age_s: Minimum seconds since the last write before a file counts as
            abandoned.

    Returns:
        Number of files removed.
    """
    if not os.path.isdir(chunks_dir):
        return 0
    cutoff = time.time() - min_age_s
    removed = 0
    for name in os.listdir(chunks_dir):
        if not (name.startswith("session_") and name.endswith((".pcm", ".wav"))):
            continue
        path = os.path.join(chunks_dir, name)
        try:
            if os.path.abspath(path) in active_paths:
                continue
            if os.path.getmtime(path) > cutoff:
                continue
            os.remove(path)
            removed += 1
        except OSError:
            pass
    if removed:
        logger.info("Removed %d orphaned chunk file(s)", removed)
    return removed
