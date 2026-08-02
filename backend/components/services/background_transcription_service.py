"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

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
import json
import os
import subprocess

# Third party
from sqlmodel import select

# Custom imports
from backend.components.llm.llm_model import SummarizeModel
from backend.components.models.categories import Categories  # noqa: E402
from backend.components.models.llm_settings_model import LlmSettingsModel
from backend.components.models.record_model import Record
from backend.components.modules.logger import get_logger
from backend.components.services.asr_factory import get_final_backend
from backend.components.services.sanitizing_service import (
    _PRESERVE_TOKENS_INSTRUCTION,
    reinject,
    sanitize,
)
from backend.components.services.settings_service import (
    get_audio_settings,
    get_whisper_params,
)
from backend.components.services.task_service import update_task_status
from backend.components.sql.sql_engine import get_session_factory

logger = get_logger(__name__)
session_factory = get_session_factory()
AUDIO_DIR = "audio"
os.makedirs(AUDIO_DIR, exist_ok=True)


def _sanitize_filename(filename: str) -> str:
    """Remove/rename characters unsafe for filesystems and HTTP headers."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")
    return filename[:200]


def _persist_audio_as_mp3(file_path: str, record: Record) -> str | None:
    """Convert audio to MP3 and persist for download.

    Args:
        file_path: Path to source audio file (WAV or any ffmpeg-compatible format).
        record: Record instance to update with the persisted file path.

    Returns:
        Path to the persisted MP3 file, or None if disabled or conversion failed.
    """
    audio_settings = get_audio_settings()
    if not audio_settings.audio_download_enabled:
        return None

    try:
        out_path = os.path.join(AUDIO_DIR, f"record_{record.id}.mp3")
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            file_path,
            "-ac",
            "1",
            "-ar",
            str(audio_settings.audio_sample_rate or 16000),
            "-b:a",
            audio_settings.audio_bitrate or "64k",
            "-loglevel",
            "error",
            out_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out_path
    except (subprocess.CalledProcessError, OSError) as e:
        logger.warning(
            f"[TASK] Failed to convert audio to MP3 for record {record.id}: {e}"
        )
        return None


def background_transcription_task(
    task_id: int,
    session_id: str,
    pcm_buffer: bytes | None,
    file_path: str | None = None,
):
    db = session_factory()

    text = ""

    # Get the right record
    smt = select(Record).where(Record.session_id == session_id)
    record = db.exec(smt).one_or_none()

    # Get category config if set
    category_prompt = None          # → LLM system prompt
    category_whisper_prompt = None  # → Whisper initial_prompt (vocabulary hints)
    category_llm_override = None
    if record and record.category_id:
        cat = db.get(Categories, record.category_id)
        if cat:
            category_prompt = cat.system_prompt
            category_whisper_prompt = cat.whisper_prompt or None
            if cat.llm_override_enabled and cat.llm_model:
                category_llm_override = cat

    try:
        backend = get_final_backend()
        logger.info(
            f"[TASK {task_id}] Starting final transcription for session={session_id}"
        )

        update_task_status(db, task_id, "transcribing")

        final_params = get_whisper_params(live=False)
        if file_path:
            text = backend.transcribe(
                file_path, prompt=category_whisper_prompt, params=final_params
            )
        elif pcm_buffer:
            text = backend.transcribe(
                pcm_buffer, prompt=category_whisper_prompt, params=final_params
            )
        else:
            raise ValueError("No audio source provided (pcm_buffer or file_path)")

        if record:
            record.content = text
            db.add(record)
            db.commit()
            db.refresh(record)
            logger.info(f"[TASK {task_id}] Transcription completed ({len(text)} chars)")

        update_task_status(db, task_id, "processing_llm")

        # Sanitize PII before LLM if EntityGuard is configured
        llm_settings = db.exec(select(LlmSettingsModel)).first()
        text_for_llm = text
        entity_mapping: dict[str, str] = {}

        if llm_settings and llm_settings.sanitizer_enabled and llm_settings.sanitizer_endpoint:
            logger.info(f"[TASK {task_id}] Running EntityGuard sanitizer")
            text_for_llm, entity_mapping = sanitize(
                text=text,
                endpoint=llm_settings.sanitizer_endpoint,
                api_key=llm_settings.sanitizer_api_key,
            )
            logger.info(f"[TASK {task_id}] Sanitized {len(entity_mapping)} entities")
            if record and entity_mapping:
                record.pii_mapping = json.dumps(entity_mapping, ensure_ascii=False)
                db.add(record)
                db.commit()

        # LLM summarization — use category-specific LLM if override is active
        if category_llm_override:
            model = SummarizeModel(
                model_name=category_llm_override.llm_model,
                base_url=category_llm_override.llm_api_endpoint,
                api_key=category_llm_override.llm_api_key,
                temperature=category_llm_override.llm_temperature,
                max_tokens=category_llm_override.llm_max_tokens,
            )
        else:
            model = SummarizeModel()

        effective_prompt = (category_prompt or "") + (
            _PRESERVE_TOKENS_INSTRUCTION if entity_mapping else ""
        )
        summary = model.generate_response(
            text_for_llm,
            custom_system_prompt=effective_prompt or None,
        )

        if entity_mapping:
            summary = reinject(summary, entity_mapping)
            logger.info(f"[TASK {task_id}] Re-injected PII into summary")

        logger.info(f"[TASK {task_id}] Summarization completed ({len(summary)} chars)")

        if record:
            record.summarize = summary
            db.add(record)
            db.commit()
            db.refresh(record)

        update_task_status(db, task_id, "finished")

        if record and file_path:
            mp3_path = _persist_audio_as_mp3(file_path, record)
            if mp3_path and os.path.exists(mp3_path):
                record.file = mp3_path
                db.add(record)
                db.commit()
                logger.info(
                    f"[TASK {task_id}] Audio persisted for download: {mp3_path}"
                )

        # Delete audio file after successful processing — patient audio must not persist
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"[TASK {task_id}] Audio file deleted: {file_path}")
            except OSError as e:
                logger.warning(f"[TASK {task_id}] Could not delete audio file {file_path}: {e}")

    except Exception as e:
        logger.error(
            f"[TASK {task_id}] Error during transcription/llm: {e}", exc_info=True
        )
        try:
            db.rollback()
            update_task_status(db, task_id, "error", error=str(e))
        except Exception as inner:
            logger.error(f"[TASK {task_id}] Failed to set error status: {inner}")

    finally:
        db.close()
