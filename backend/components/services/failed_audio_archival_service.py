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
"""

# Standard library
import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone

# Third-party
from sqlmodel import select

# Custom
from backend.components.models.task_model import Task
from backend.components.modules.logger import get_logger
from backend.components.security.field_encryption import encrypt_bytes
from backend.components.services import audio_storage
from backend.components.services.background_transcription_service import (
    _build_ffmpeg_args,
)
from backend.components.services.settings_service import get_audio_settings
from backend.components.sql.sql_engine import get_session_factory

logger = get_logger(__name__)
session_factory = get_session_factory()

_warned_unconfigured = False


def _encode_for_archive(
    file_path: str, fmt: str, bitrate: str, sample_rate: int
) -> tuple[bytes, str]:
    """Return (archive-ready bytes, file extension) for ``file_path``.

    Skips ffmpeg entirely when the source is already the target format — the
    common case, since ``finalize()`` always converts live recordings to WAV
    before handing off to ``background_transcription_task``. Unlike the
    clinician-download copy in ``_persist_audio()``, the archive copy is a
    faithful backup of the original, not a compressed download, so no
    resampling is applied in that case either.
    """
    if fmt == "wav" and file_path.lower().endswith(".wav"):
        with open(file_path, "rb") as f:
            return f.read(), "wav"

    codec_args, ext = _build_ffmpeg_args(fmt, bitrate)
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            file_path,
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            *codec_args,
            "-loglevel",
            "error",
            tmp_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        with open(tmp_path, "rb") as f:
            return f.read(), ext
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def archive_stale_failed_audio(retention_days: int) -> int:
    """Move ``chunks/failed/`` audio older than ``retention_days`` to S3.

    Only touches tasks with ``status == "error"`` and a local (not yet
    archived) ``retry_audio_path`` — retention for successfully processed
    recordings is unrelated: those are deleted immediately elsewhere
    (``background_transcription_service.py``) for DSGVO/§203 StGB data
    minimization and never reach this table.

    Args:
        retention_days: Age threshold (based on ``Task.updated_at``) beyond
            which a still-unretried failed task's local audio is archived.

    Returns:
        Number of tasks archived.
    """
    global _warned_unconfigured
    if not audio_storage.is_configured():
        if not _warned_unconfigured:
            logger.warning(
                "S3 storage not configured — failed-task audio archival is "
                "disabled; chunks/failed/ files will accumulate indefinitely "
                "until retried."
            )
            _warned_unconfigured = True
        return 0

    audio_settings = get_audio_settings()
    fmt = (audio_settings.audio_format or "mp3").lower()
    bitrate = audio_settings.audio_bitrate or "64k"
    sample_rate = audio_settings.audio_sample_rate or 16000

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    db = session_factory()
    archived = 0
    try:
        tasks = db.exec(
            select(Task).where(
                Task.status == "error",
                Task.retry_audio_path.is_not(None),
                Task.retry_audio_in_s3.is_(False),
                Task.updated_at < cutoff,
            )
        ).all()

        for task in tasks:
            file_path = task.retry_audio_path
            if not file_path or not os.path.exists(file_path):
                continue
            try:
                data, ext = _encode_for_archive(file_path, fmt, bitrate, sample_rate)
                key = f"archive/task_{task.id}.{ext}.enc"
                audio_storage.upload_bytes(key, encrypt_bytes(data))
                os.remove(file_path)
                task.retry_audio_path = key
                task.retry_audio_in_s3 = True
                db.add(task)
                db.commit()
                archived += 1
                logger.info(f"[TASK {task.id}] Archived retained audio to S3: {key}")
            except (OSError, subprocess.CalledProcessError, RuntimeError) as e:
                db.rollback()
                logger.warning(
                    f"[TASK {task.id}] Failed to archive retained audio: {e}"
                )
    finally:
        db.close()

    return archived
