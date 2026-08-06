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
import tempfile

# Third party
from sqlmodel import select

# Custom imports
from backend.components.llm.llm_model import SummarizeModel
from backend.components.models.categories import Categories  # noqa: E402
from backend.components.models.llm_settings_model import LlmSettingsModel
from backend.components.models.record_model import Record
from backend.components.models.task_model import Task
from backend.components.modules.logger import get_logger
from backend.components.security.field_encryption import encrypt_bytes
from backend.components.services import audio_storage
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


def _sanitize_filename(filename: str) -> str:
    """Remove/rename characters unsafe for filesystems and HTTP headers."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")
    return filename[:200]


def _build_ffmpeg_args(fmt: str, bitrate: str) -> tuple[list[str], str]:
    """Return (codec/bitrate ffmpeg args, file extension) for an audio format.

    Falls back to mp3 for unknown/empty values so old settings rows without
    the audio_format column keep working.
    """
    if fmt == "wav":
        return ["-c:a", "pcm_s16le"], "wav"
    if fmt == "flac":
        return ["-c:a", "flac", "-compression_level", "8"], "flac"
    if fmt == "ogg":
        return ["-c:a", "libopus", "-b:a", bitrate], "ogg"
    return ["-c:a", "libmp3lame", "-b:a", bitrate], "mp3"


def _persist_audio(file_path: str, record: Record) -> str | None:
    """Convert audio to the configured format, encrypt it, and upload to S3.

    Args:
        file_path: Path to source audio file (WAV or any ffmpeg-compatible format).
        record: Record instance the persisted audio belongs to.

    Returns:
        The S3 object key the encrypted audio was stored under, or None if
        disabled or conversion/upload failed.
    """
    audio_settings = get_audio_settings()
    if not audio_settings.audio_download_enabled:
        return None

    fmt = (audio_settings.audio_format or "mp3").lower()
    codec_args, ext = _build_ffmpeg_args(fmt, audio_settings.audio_bitrate or "64k")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp_path = tmp.name
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            file_path,
            "-ac",
            "1",
            "-ar",
            str(audio_settings.audio_sample_rate or 16000),
            *codec_args,
            "-loglevel",
            "error",
            tmp_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        with open(tmp_path, "rb") as f:
            plaintext = f.read()

        key = f"records/{record.id}.{ext}.enc"
        audio_storage.upload_bytes(key, encrypt_bytes(plaintext))
        return key
    except (subprocess.CalledProcessError, OSError, RuntimeError) as e:
        logger.warning(
            f"[TASK] Failed to persist audio to S3 for record {record.id}: {e}"
        )
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def _should_overwrite_content(new_text: str, existing_content: str | None) -> bool:
    """Decide whether a fresh transcription result should replace ``record.content``.

    An empty Whisper result (corrupt/near-empty audio, a bad retry) must not
    silently clobber a transcript that's already there — but a genuinely
    empty first run still needs to store the empty result.
    """
    return bool(new_text.strip()) or not bool((existing_content or "").strip())


def _retain_audio_for_retry(db, task_id: int, file_path: str) -> None:
    """Move a failed task's source audio out of the ephemeral scratch dir.

    Keeps it out of reach of the session/startup cleanup loops (which only
    match ``session_*`` files at the top level of their scratch dir) and
    records its new location on the Task so ``POST /tasks/{id}/retry`` can
    find it again.
    """
    if not file_path or not os.path.exists(file_path):
        return
    try:
        parent = os.path.dirname(file_path) or "."
        # A retried task that fails again already lives under .../failed —
        # reuse that dir instead of nesting failed/failed/...
        failed_dir = (
            parent
            if os.path.basename(parent) == "failed"
            else os.path.join(parent, "failed")
        )
        os.makedirs(failed_dir, exist_ok=True)
        ext = os.path.splitext(file_path)[1]
        retry_path = os.path.join(failed_dir, f"task_{task_id}{ext}")
        if os.path.abspath(retry_path) != os.path.abspath(file_path):
            os.replace(file_path, retry_path)
        task = db.get(Task, task_id)
        if task:
            task.retry_audio_path = retry_path
            db.add(task)
            db.commit()
        logger.warning(f"[TASK {task_id}] Kept audio for retry: {retry_path}")
    except OSError as e:
        logger.error(f"[TASK {task_id}] Failed to retain audio for retry: {e}")


def background_transcription_task(
    task_id: int,
    session_id: str,
    pcm_buffer: bytes | None,
    file_path: str | None = None,
) -> bool:
    """Run transcription → PII sanitize → LLM summary → audio persist.

    Returns:
        True if the task reached "finished", False if any step raised. The
        caller (``finalize()``/``run_pipeline()``/the retry endpoint) uses
        this to decide whether to delete ``file_path`` or keep it — the
        actual deletion/retention happens inside this function itself, see
        the end of the try block and ``_retain_audio_for_retry``.
    """
    db = session_factory()

    text = ""

    # Get the right record
    smt = select(Record).where(Record.session_id == session_id)
    record = db.exec(smt).one_or_none()

    # Get category config if set
    category_prompt = None  # → LLM system prompt
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
            if _should_overwrite_content(text, record.content):
                record.content = text
                db.add(record)
                db.commit()
                db.refresh(record)
                logger.info(
                    f"[TASK {task_id}] Transcription completed ({len(text)} chars)"
                )
            else:
                logger.warning(
                    f"[TASK {task_id}] Empty transcription result, "
                    "keeping existing content"
                )

        update_task_status(db, task_id, "processing_llm")

        # Sanitize PII before LLM if EntityGuard is configured
        llm_settings = db.exec(select(LlmSettingsModel)).first()
        text_for_llm = text
        entity_mapping: dict[str, str] = {}

        if (
            llm_settings
            and llm_settings.sanitizer_enabled
            and llm_settings.sanitizer_endpoint
        ):
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
            s3_key = _persist_audio(file_path, record)
            if s3_key:
                record.file = s3_key
                db.add(record)
                db.commit()
                logger.info(f"[TASK {task_id}] Audio persisted for download: {s3_key}")

        # Delete audio file after successful processing — patient audio must not persist
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"[TASK {task_id}] Audio file deleted: {file_path}")
            except OSError as e:
                logger.warning(
                    f"[TASK {task_id}] Could not delete audio file {file_path}: {e}"
                )

        return True

    except Exception as e:
        logger.error(
            f"[TASK {task_id}] Error during transcription/llm: {e}", exc_info=True
        )
        try:
            db.rollback()
            update_task_status(db, task_id, "error", error=str(e))
            if file_path:
                _retain_audio_for_retry(db, task_id, file_path)
        except Exception as inner:
            logger.error(f"[TASK {task_id}] Failed to set error status: {inner}")
        return False

    finally:
        db.close()
