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


Audio kept after a failed transcription so an admin can retry it.

``Task.retry_audio_path`` is a local file under ``chunks/failed/`` or, once
archived (``Task.retry_audio_in_s3``), an S3 key under ``archive/``. Both
helpers split the removal in two so callers can delete the bytes only after
their DB change is committed — a failed commit must never lose the audio.
"""

# Standard library
import os

# Custom
from backend.components.models.task_model import Task
from backend.components.modules.logger import get_logger
from backend.components.services import audio_storage

logger = get_logger(__name__)

RetainedAudio = tuple[str, bool]


def detach_retained_audio(task: Task) -> RetainedAudio | None:
    """Clear the task's retained-audio reference and return it (path, in_s3).

    The caller commits the task, then passes the result to
    :func:`remove_retained_audio`. ``None`` if nothing was retained.
    """
    if not task.retry_audio_path:
        return None
    retained = (task.retry_audio_path, task.retry_audio_in_s3)
    task.retry_audio_path = None
    task.retry_audio_in_s3 = False
    return retained


def remove_retained_audio(retained: RetainedAudio | None) -> None:
    """Delete the bytes returned by :func:`detach_retained_audio` (fail-open)."""
    if retained is None:
        return
    path, in_s3 = retained
    try:
        if in_s3:
            audio_storage.delete(path)
        elif os.path.exists(path):
            os.remove(path)
        logger.info(f"[RETAINED AUDIO] Removed {path}")
    except Exception as e:
        logger.warning(f"[RETAINED AUDIO] Could not remove {path}: {e}")
