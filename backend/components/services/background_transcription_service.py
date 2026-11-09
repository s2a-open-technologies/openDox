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

# Standard library
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone

# Third party
from sqlmodel import select

# Custom imports
from backend.components.llm.llm_model import SummarizeModel
from backend.components.models.record_model import Record
from backend.components.models.task_model import Task
from backend.components.modules.logger import get_logger
from backend.components.security.field_encryption import decrypt_bytes, encrypt_bytes
from backend.components.services import audio_storage
from backend.components.services.asr_factory import get_final_backend
from backend.components.services.dictionary_service import glossary_for_category
from backend.components.services.llm_gate import (
    category_llm_enabled,
    effective_category,
    llm_globally_enabled,
    run_summary,
    sanitize_if_configured,
)
from backend.components.services.sanitizing_service import reinject
from backend.components.services.settings_service import (
    get_audio_settings,
    get_settings,
    get_whisper_params,
)
from backend.components.services.task_service import update_task_status
from backend.components.services.term_correction_service import correct_terms
from backend.components.services.translation import check_segment, translate
from backend.components.services.translation.segmenter import join_sentences
from backend.components.services.translation_gate import target_language
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


def _archive_failed_audio_to_s3(db, task_id: int, file_path: str) -> bool:
    """Upload a failed task's audio to S3 right away, if S3 is configured.

    With several app instances the admin's retry request can land on any of
    them, so the audio must not stay on the local disk of the instance that
    happened to run the task. Returns False (caller keeps it locally) when S3
    is not configured or the upload fails: a recording is never dropped because
    the object store is down.
    """
    # Imported here: failed_audio_archival_service imports this module.
    from backend.components.services import failed_audio_archival_service as archive

    if not archive.audio_storage.is_configured():
        return False
    try:
        key = archive.archive_task_audio(task_id, file_path)
        task = db.get(Task, task_id)
        if task:
            task.retry_audio_path = key
            task.retry_audio_in_s3 = True
            db.add(task)
            db.commit()
    except Exception as e:
        db.rollback()
        logger.error(
            f"[TASK {task_id}] S3 upload of failed audio failed, keeping it "
            f"locally: {e}"
        )
        return False

    logger.warning(f"[TASK {task_id}] Kept audio for retry in S3: {key}")
    try:
        os.remove(file_path)
    except OSError as e:
        # The task already points at S3; a leftover scratch file is harmless
        # (the orphan cleanup removes it).
        logger.warning(f"[TASK {task_id}] Could not delete local audio: {e}")
    return True


def _retain_audio_for_retry(db, task_id: int, file_path: str) -> None:
    """Move a failed task's source audio out of the ephemeral scratch dir.

    Keeps it out of reach of the session/startup cleanup loops (which only
    match ``session_*`` files at the top level of their scratch dir) and
    records its new location on the Task so ``POST /tasks/{id}/retry`` can
    find it again.
    """
    if not file_path or not os.path.exists(file_path):
        return
    if _archive_failed_audio_to_s3(db, task_id, file_path):
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


def resolve_failed_task(db, record: Record) -> str | None:
    """Mark a record's failed task as finished once the record is complete.

    Called after the user regenerated the summary of a recording whose
    pipeline had failed (typically the LLM step): the recording now has
    transcript and summary, so the "error" state would otherwise stick
    forever. The audio retained for the admin retry is no longer needed:
    with audio download enabled it becomes the record's download audio
    (``_persist_audio``, which the failed run never reached), otherwise it is
    deleted. It is only deleted after the task change is committed, so a
    failing commit never loses the recording.

    Returns:
        The task's status afterwards, or None if the record has no task.
    """
    if not record.task_id:
        return None
    task = db.get(Task, record.task_id)
    if task is None or task.status != "error":
        return task.status if task else None

    retained_key = task.retry_audio_path if task.retry_audio_in_s3 else None
    retained_local = task.retry_audio_path if not task.retry_audio_in_s3 else None
    tmp_path = None
    try:
        source = retained_local
        if retained_key:
            encrypted = audio_storage.download_bytes(retained_key)
            if encrypted is not None:
                ext = os.path.basename(retained_key).split(".")[-2]
                with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                    tmp.write(decrypt_bytes(encrypted))
                    tmp_path = tmp.name
                source = tmp_path
        if source and os.path.exists(source) and not record.file:
            s3_key = _persist_audio(source, record)
            if s3_key:
                record.file = s3_key
                db.add(record)

        task.status = "finished"
        task.error = None
        task.retry_audio_path = None
        task.retry_audio_in_s3 = False
        task.updated_at = datetime.now(timezone.utc)
        db.add(task)
        db.commit()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    if retained_key:
        audio_storage.delete(retained_key)
    elif retained_local and os.path.exists(retained_local):
        os.remove(retained_local)
    logger.info(f"[TASK {task.id}] Resolved after summary regeneration")
    return task.status


def _source_language(record: Record | None, target: str) -> str | None:
    """Dictation language if the record is to be translated, else None."""
    source = (record.source_language or "").lower() if record else ""
    return source if source and source != target else None


def _correct_terms(
    db, cat, record: Record | None, texts: list[str], task_id: int
) -> list[str]:
    """Phonetic term correction of German texts (fail-open, see module docs).

    Returns the texts unchanged when it is switched off, finds no glossary or
    fails.
    """
    whisper_settings = get_settings()
    if not whisper_settings.term_correction_enabled:
        return texts
    try:
        # The category's dictionaries plus all personal dictionaries of the
        # recording's owner — whisper_prompt never feeds it.
        glossary = glossary_for_category(db, cat, record.user_id if record else None)
        if not glossary:
            return texts
        corrected = []
        for text in texts:
            text, replacements = correct_terms(
                text, glossary, whisper_settings.term_correction_threshold
            )
            for r in replacements:
                logger.info(
                    f"[TASK {task_id}] Fachbegriff-Korrektur: "
                    f"{r['original']!r} -> {r['replacement']!r} "
                    f"(score={r['score']:.1f})"
                )
            corrected.append(text)
        return corrected
    except Exception:
        logger.warning(
            f"[TASK {task_id}] term_correction_service failed, using uncorrected text",
            exc_info=True,
        )
        return texts


def _translate_record(
    db,
    cat,
    record: Record | None,
    text: str,
    source: str,
    target: str,
    task_id: int,
) -> str:
    """Translate the transcript into the instance language and store it.

    ``content`` keeps the original. Raises on any LLM error, so the task ends
    in "error" with the transcript already saved.

    Returns:
        The translated text (what the summary is built from).
    """
    # Names are masked like for the summary, fail-closed: an unreachable
    # sanitizer raises, the original never reaches the LLM unmasked.
    masked, entity_mapping = sanitize_if_configured(db, text)
    model = SummarizeModel(enable_thinking=False)
    result = translate(
        masked,
        source,
        target,
        complete=model.complete,
        preserve_tokens=bool(entity_mapping),
    )
    segments = result.segments
    if entity_mapping:
        # Real names back into both sides, then check the numbers again
        # (digits inside tokens like [PERSON_1] must not count).
        segments = [
            check_segment(
                reinject(s.source, entity_mapping),
                reinject(s.target, entity_mapping),
                s.paragraph,
            )
            for s in segments
        ]
        result.text = join_sentences(
            [s.target for s in segments], [s.paragraph for s in segments]
        )
    if target == "de":
        corrected = _correct_terms(
            db, cat, record, [s.target for s in segments], task_id
        )
        for segment, fixed in zip(segments, corrected):
            segment.target = fixed
        result.text = join_sentences(corrected, [s.paragraph for s in segments])
    flagged = sum(1 for s in segments if s.flagged)
    logger.info(
        f"[TASK {task_id}] Translation {source}->{target} completed "
        f"({len(segments)} sentences, {flagged} with differing numbers)"
    )
    if record:
        record.translation = result.text
        record.translation_language = target
        record.translation_segments = json.dumps(
            [s.to_dict() for s in segments], ensure_ascii=False
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    return result.text


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
    category_whisper_prompt = None  # → Whisper initial_prompt (vocabulary hints)
    # A personal category counts as none unless the operator allows them.
    cat = effective_category(db, record)
    if cat:
        category_whisper_prompt = cat.whisper_prompt or None

    try:
        backend = get_final_backend()
        logger.info(
            f"[TASK {task_id}] Starting final transcription for session={session_id}"
        )

        update_task_status(db, task_id, "transcribing")

        # Dictated in another language: Whisper gets that language and no
        # category prompt (its vocabulary hints are in the instance language).
        target = target_language(db)
        source = _source_language(record, target)
        text_language = source or target
        prompt = None if source else category_whisper_prompt

        final_params = get_whisper_params()
        if file_path:
            text = backend.transcribe(
                file_path, language=text_language, prompt=prompt, params=final_params
            )
        elif pcm_buffer:
            text = backend.transcribe(
                pcm_buffer, language=text_language, prompt=prompt, params=final_params
            )
        else:
            raise ValueError("No audio source provided (pcm_buffer or file_path)")

        # Kölner Phonetik only works on German text.
        if text_language == "de":
            text = _correct_terms(db, cat, record, [text], task_id)[0]

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

        result = text
        if source and text.strip():
            update_task_status(db, task_id, "translating")
            result = _translate_record(db, cat, record, text, source, target, task_id)

        if not llm_globally_enabled(db) or not category_llm_enabled(cat):
            # Transcription only: summarize stays empty, the API serves the
            # transcript in its place (llm_gate.effective_summary).
            logger.info(f"[TASK {task_id}] LLM disabled (global/category), skipped")
        else:
            update_task_status(db, task_id, "processing_llm")
            summary, entity_mapping = run_summary(db, cat, result)
            logger.info(
                f"[TASK {task_id}] Summarization completed ({len(summary)} chars, "
                f"{len(entity_mapping)} sanitized entities)"
            )
            if record:
                if entity_mapping:
                    record.pii_mapping = json.dumps(entity_mapping, ensure_ascii=False)
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
