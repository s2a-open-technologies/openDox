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
import asyncio
import json
import os
import shutil
import time

# Third party
import uuid
from datetime import datetime

import numpy as np
from fastapi import File, Form, HTTPException, UploadFile, WebSocket
from sqlalchemy import desc as _sql_desc
from sqlmodel import select

from backend.components.llm.llm_model import OllamaModel
from backend.components.models.categories import Categories
from backend.components.models.llm_settings_model import LlmSettingsModel
from backend.components.models.record_model import (
    Record,
    RecordCreate,
    RecordRead,
    RecordUpdate,
)
from backend.components.models.task_model import Task
from backend.components.modules.audio import normalize_quiet_pcm
from backend.components.modules.logger import get_logger
from backend.components.modules.text_dedup import merge_overlapping_text
from backend.components.services.asr_factory import get_final_backend, get_live_backend
from backend.components.services.background_transcription_service import (
    background_transcription_task,
)
from backend.components.services.sanitizing_service import (
    _PRESERVE_TOKENS_INSTRUCTION,
    reinject,
    sanitize,
)
from backend.components.services.session_store import session_store
from backend.components.sql.sql_engine import SessionDep

# Custom imports
from backend.views.record_api import record_bp

logger = get_logger(__name__)


async def _run_periodic_cleanup(session_id: str, websocket: WebSocket) -> None:
    """Smooth chunk-boundary punctuation in the live transcript via LLM (non-blocking)."""
    from backend.components.services.chunk_correction_service import smooth_transcript

    session = session_store.get_by_session(session_id)
    if not session:
        return
    snapshot = session.get("live_text", "").strip()
    if not snapshot:
        return
    try:
        cleaned = await asyncio.to_thread(smooth_transcript, snapshot)
        if not cleaned or cleaned == snapshot:
            return
        session = session_store.get_by_session(session_id)
        if not session:
            return
        current = session.get("live_text", "")
        if current.startswith(snapshot):
            tail = current[len(snapshot) :]
            new_text = (cleaned + tail).strip()
        else:
            new_text = cleaned
        session_store.set_live_state(session_id, session.get("last_index", 0), new_text)
        await websocket.send_json({"session_id": session_id, "cleanup": new_text})
        logger.info("[SMOOTH] cleanup sent (%d chars)", len(new_text))
    except Exception as e:
        logger.debug("[SMOOTH] failed: %s", e)


OUTPUT_DIR = "chunks"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _pcm_file_to_wav_file(pcm_path: str, wav_path: str) -> None:
    """Convert a float32 raw PCM file to a 16-bit 16 kHz mono WAV file."""
    import struct

    with open(pcm_path, "rb") as f:
        float_arr = np.frombuffer(f.read(), dtype=np.float32)
    float_arr = normalize_quiet_pcm(float_arr)
    int16_arr = (float_arr * 32767).astype(np.int16)
    data_size = len(int16_arr) * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        16000,
        32000,
        2,
        16,
        b"data",
        data_size,
    )
    with open(wav_path, "wb") as f:
        f.write(header + int16_arr.tobytes())


def get_live_asr():
    """Get the live ASR backend based on current settings."""
    return get_live_backend()


def get_final_asr():
    """Get the final ASR backend based on current settings."""
    return get_final_backend()


@record_bp.post("/create")
async def record_create(db: SessionDep, data: RecordCreate):
    """Creates a new record

    Parameters:
        payload (str): Payload with user_id and session_id and title
    """
    # Create a unique session_id
    session_id = uuid.uuid4()

    # Creates a new record in database
    record = Record(
        session_id=str(session_id),
        user_id=data.user_id,
        category_id=data.category_id,
        title=data.title,
        timestamp=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        content="",
        summarize="",
        file="",
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    # Register the active recording session in the store.
    # This is the single source of truth for an "unfinished recording".
    session_store.create_session(
        user_id=data.user_id,
        session_id=str(session_id),
        record_id=record.id,
        title=record.title,
        category_id=record.category_id,
        audio_dir=OUTPUT_DIR,
    )

    return record


@record_bp.get("/active-session/{user_id}")
async def active_session(user_id: int):
    """Return the user's active (unfinished) recording session, if any.

    Drives the "unfinished recording" indicator in the sidebar.
    """
    session = session_store.get_session(user_id)
    if not session:
        return {"active": False}

    return {
        "active": True,
        "session_id": session["session_id"],
        "record_id": session["record_id"],
        "title": session["title"],
        "category_id": session["category_id"],
        "status": session["status"],
    }


@record_bp.delete("/cancel-session/{user_id}")
async def cancel_session(user_id: int, db: SessionDep):
    """Cancel an unfinished recording.

    Deletes the live session from the store, the DB record and the audio files
    on disk for that session.
    """
    session = session_store.get_session(user_id)
    if not session:
        return {"status": "no_active_session"}

    session_id = session["session_id"]
    record_id = session.get("record_id")

    # 1. Delete the DB record
    if record_id is not None:
        record = db.get(Record, record_id)
        if record:
            db.delete(record)
            db.commit()

    # 2. Remove the live session from the store — also deletes the PCM file on disk
    session_store.delete_session(user_id)

    return {"status": "cancelled", "session_id": session_id}


# Websocket Connection for live transcription
@record_bp.websocket("/ws/record")
async def websocket_record(websocket: WebSocket, db: SessionDep):
    """Websocket for partial transcribing and saving into buffer"""
    await websocket.accept()

    session_id = websocket.query_params.get("session_id")
    user_id = websocket.query_params.get("user_id")

    if not session_id or not user_id:
        try:
            await websocket.send_json({"error": "session_id and user_id required"})
            await websocket.close()
        except Exception:
            pass
        return

    try:
        user_id_int = int(user_id)
    except ValueError:
        try:
            await websocket.send_json({"error": "user_id must be an integer"})
            await websocket.close()
        except Exception:
            pass
        return

    print(f"[WS-START] user={user_id}, session={session_id}")

    # Get the active recording session (live state lives in the store).
    # On a resume the session already exists and carries the prior live text.
    session = session_store.get_by_session(session_id)
    if session is None:
        # Store was cleared (e.g. server restart) - rebuild from the DB record so
        # live transcription keeps working across reconnects.
        record = db.exec(
            select(Record).where(Record.session_id == session_id)
        ).one_or_none()
        if record:
            session = session_store.create_session(
                user_id=user_id_int,
                session_id=session_id,
                record_id=record.id,
                title=record.title,
                category_id=record.category_id,
                audio_dir=OUTPUT_DIR,
            )

    client_connected = True
    stopped = False

    # Cache session state locally to avoid Redis round-trips on every audio chunk.
    # Per-chunk Redis calls (10+ ops at ~0.5–2ms each) saturate the event loop at
    # 125 chunks/second and cause the WebSocket to stall under the proxy.
    local_audio_path: str = session["audio_file_path"] if session else ""
    local_audio_size: int = session["audio_file_size"] if session else 0
    local_last_index: int = session["last_index"] if session else 0
    local_live_text: str = session.get("live_text", "") if session else ""
    local_user_id: int = session["user_id"] if session else user_id_int
    last_cleanup_time: float = session.get("last_cleanup_time", 0.0) if session else 0.0
    last_cleanup_len: int = session.get("last_cleanup_len", 0) if session else 0

    # On resume: push the accumulated transcript back so the client gets it again.
    if session and session.get("live_text"):
        try:
            await websocket.send_json(
                {
                    "session_id": session_id,
                    "text": session["live_text"],
                    "restored": True,
                }
            )
        except Exception as e:
            print(f"[WS-RESTORE-ERROR] {e}")

    try:
        while True:
            msg = await websocket.receive()

            # Disconnect Message
            if msg["type"] == "websocket.disconnect":
                print(f"[WS-DISCONNECT] session={session_id}")
                client_connected = False
                break

            # Text Message
            if msg.get("text"):
                data = msg["text"]

                # Stop event -> beende die Aufnahme
                if "stop" in data:
                    print("[WS] Stop event received")
                    stopped = True
                    break

                continue  # andere Textnachrichten ignorieren

            # Binary Message
            if msg.get("bytes"):
                chunk = msg["bytes"]

                if not chunk:
                    print("[WARNING] Empty binary chunk received")
                    continue

                if not local_audio_path:
                    continue

                # Write audio directly to disk — no Redis round-trip per chunk.
                with open(local_audio_path, "ab") as _af:
                    _af.write(chunk)
                local_audio_size += len(chunk)

                # Live ASR
                try:
                    backend = get_live_asr()

                    # chunk_length_s * 16000 samples/s * 4 bytes/sample (float32)
                    bytes_per_chunk = 3 * 16000 * 4  # default 3s chunks
                    bytes_per_overlap = 0
                    bytes_per_left_context = 0
                    is_parakeet = False
                    whisper_params = None
                    try:
                        from backend.components.services.settings_service import (
                            get_settings,
                            get_whisper_params,
                        )

                        settings = get_settings()
                        bytes_per_chunk = settings.chunk_length_s * 16000 * 4
                        bytes_per_overlap = int(settings.overlap_s * 16000 * 4)
                        if settings.live_backend == "parakeet":
                            bytes_per_overlap = 0
                            is_parakeet = True
                            bytes_per_left_context = int(
                                settings.left_context_s * 16000 * 4
                            )
                        whisper_params = get_whisper_params(live=True)
                    except Exception:
                        pass

                    new_data_len = local_audio_size - local_last_index

                    if new_data_len >= bytes_per_chunk:
                        start = local_last_index
                        # Read some extra audio from before `start` as pure
                        # acoustic context for Parakeet — this does NOT move
                        # `start`/`new_index`, it's read-only look-back.
                        read_start = max(0, start - bytes_per_left_context)
                        read_len = (start - read_start) + bytes_per_chunk
                        with open(local_audio_path, "rb") as _f:
                            _f.seek(read_start)
                            audio_slice = _f.read(read_len)
                        new_index = start + bytes_per_chunk - bytes_per_overlap

                        # Normalize quiet audio so Whisper doesn't hallucinate
                        # filler phrases instead of returning silence.
                        _pcm = np.frombuffer(audio_slice, dtype=np.float32)
                        audio_slice = normalize_quiet_pcm(_pcm).tobytes()

                        # Whisper tends to repeat text from the prompt, causing
                        # duplication in the live transcript. Skip the prompt.
                        _ = None  # live_prompt intentionally unused

                        logger.info(
                            "[ASR] chunk %.1fs | overlap %.1fs | "
                            "left_ctx %.1fs | params=%s",
                            len(audio_slice) / (16000 * 4),
                            bytes_per_overlap / (16000 * 4),
                            bytes_per_left_context / (16000 * 4),
                            whisper_params,
                        )
                        # Transcribe in background thread (non-blocking)
                        result_text = await asyncio.to_thread(
                            backend.transcribe,
                            audio=audio_slice,
                            language="de",
                            prompt=None,
                            params=whisper_params,
                        )

                        # Always advance the index — even on empty result — so the
                        # same audio slice is never re-transcribed in the next loop.
                        local_last_index = new_index

                        if result_text:
                            if is_parakeet:
                                local_live_text = merge_overlapping_text(
                                    local_live_text, result_text
                                )
                            else:
                                local_live_text = (
                                    local_live_text + " " + result_text
                                ).strip()
                            # Persist to Redis only after transcription (~every 3s)
                            session_store.set_live_state(
                                session_id, new_index, local_live_text
                            )

                            try:
                                record = db.exec(
                                    select(Record).where(
                                        Record.session_id == session_id
                                    )
                                ).one_or_none()
                                if record:
                                    timestamp = datetime.now().strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    )
                                    record.content = (
                                        record.content or ""
                                    ) + f" [{timestamp}] {result_text}"
                                    db.add(record)
                                    db.commit()
                            except Exception as e:
                                print(f"[DB-PARTIAL-ERROR] {e}")

                            if client_connected:
                                try:
                                    await websocket.send_json(
                                        {"session_id": session_id, "text": result_text}
                                    )
                                except Exception as e:
                                    print(f"[WS-SEND-ERROR] {e}")
                                    client_connected = False

                            # Periodic LLM cleanup every 30s
                            _now = time.monotonic()
                            live_len = len(local_live_text)
                            if (
                                client_connected
                                and _now - last_cleanup_time >= 30.0
                                and live_len > last_cleanup_len
                            ):
                                last_cleanup_time = _now
                                last_cleanup_len = live_len
                                session_store.update_session(
                                    local_user_id,
                                    {
                                        "last_cleanup_time": _now,
                                        "last_cleanup_len": live_len,
                                    },
                                )
                                asyncio.create_task(
                                    _run_periodic_cleanup(session_id, websocket)
                                )

                except Exception as e:
                    print(f"[LIVE-ASR-ERROR] {e}")

                continue  # naechster Loop

            # Ignoriere sonstige Nachrichtentypen
            print(f"[WS-UNKNOWN] {msg}")
            continue

    except Exception as e:
        print(f"[WS-ERROR] {e}")
        client_connected = False

    # Plain disconnect without a "stop" event -> keep the session in the store as
    # an unfinished recording so it can be resumed later.
    # Sync the local audio size back to Redis so resume knows where to continue.
    if not stopped:
        print(f"[WS] Session {session_id} left unfinished (kept for resume)")
        session_store.update_session(
            local_user_id,
            {"audio_file_size": local_audio_size, "last_index": local_last_index},
        )
        try:
            await websocket.close()
        except Exception:
            pass
        return

    # Stop event -> finalize the recording and run the transcription workflow.
    # Use local_audio_path / local_audio_size because session may be stale —
    # audio data was written directly to disk without Redis updates per chunk.
    if local_audio_path:
        pcm_path = local_audio_path
        audio_size = local_audio_size

        # Null out audio_file_path so delete_session won't remove the PCM file —
        # the finalize task owns cleanup instead.
        session_store.update_session(user_id_int, {"audio_file_path": ""})

        session_store.delete_session(user_id_int)

        if audio_size == 0:
            try:
                os.remove(pcm_path)
            except OSError:
                pass
            print("[WARNING] Empty audio buffer received")
            if client_connected:
                try:
                    await websocket.send_json(
                        {"status": "error", "message": "No audio data received"}
                    )
                    await websocket.close()
                except Exception:
                    pass
            return

        # Task in DB
        task = Task(status="pending")
        db.add(task)
        db.commit()
        db.refresh(task)

        # Link task to record
        record = db.exec(
            select(Record).where(Record.session_id == session_id)
        ).one_or_none()
        if record:
            record.task_id = task.id
            db.add(record)
            db.commit()

        if client_connected:
            try:
                await websocket.send_json(
                    {"status": "finished", "task_id": task.id, "session_id": session_id}
                )
                print("[WS] Background Whisper processing launched (Response sent)")
            except Exception as e:
                print(f"[WS-SEND-ERROR] Failed to send finish signal: {e}")
        else:
            print("[WS] Background Whisper processing launched (Client disconnected)")

        try:
            if client_connected:
                await websocket.close()
        except Exception:
            pass

        async def finalize():
            wav_path = os.path.splitext(pcm_path)[0] + ".wav"
            try:
                print(
                    f"[FINAL] Converting {pcm_path} ({audio_size // 1024} KB PCM) → WAV"
                )
                await asyncio.to_thread(_pcm_file_to_wav_file, pcm_path, wav_path)
                # background_transcription_task deletes wav_path after transcription
                await asyncio.to_thread(
                    background_transcription_task,
                    task.id,
                    session_id,
                    None,
                    file_path=wav_path,
                )
            except Exception as e:
                print(f"[FINALIZE-ERROR] {e}")
            finally:
                try:
                    os.remove(pcm_path)
                except OSError:
                    pass

        asyncio.create_task(finalize())

    else:
        print("[ERROR] Session not found during final processing")
        try:
            await websocket.close()
        except Exception:
            pass


# Audiochunk upload
@record_bp.post("/upload-chunk")
async def record(
    db: SessionDep,
    file: UploadFile = File(...),
    user_id: int = Form(...),
    session_id: str = Form(...),
):
    """Upload audio chunk and append to session buffer.

    Rejects the upload if the session no longer exists (e.g. user cancelled),
    preventing orphaned chunk files on disk.
    """
    session = session_store.get_session(user_id)
    if not session or session.get("session_id") != session_id:
        raise HTTPException(
            status_code=409,
            detail="Session not found or already cancelled. Chunk rejected.",
        )

    actual_date = datetime.now().strftime("%Y%m%d_%H%M%S")
    chunk_filename = f"user{user_id}_session{session_id}_{actual_date}_chunk.webm"
    chunk_path = f"{OUTPUT_DIR}/{chunk_filename}"

    with open(chunk_path, "ab") as f:
        shutil.copyfileobj(file.file, f)

    return {"status": "chunk received"}


@record_bp.put("/record/{record_id}", response_model=RecordRead)
async def update_record(record_id: int, data: RecordUpdate, db: SessionDep):
    """Update an existing record (transcript, summary, title, category)"""
    record = db.get(Record, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    if data.title is not None:
        record.title = data.title
    if data.content is not None:
        record.content = data.content
    if data.summarize is not None:
        record.summarize = data.summarize
    if data.file is not None:
        record.file = data.file
    if data.category_id is not None:
        record.category_id = data.category_id

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# Route for showing records in frontend
@record_bp.get("/list-records/{user_id}")
async def list_records(user_id: int, db: SessionDep, archived: bool = False):
    """List all records for a specific user, filtering by archived status"""
    # Get the record sessions per user and archived status, newest first
    smt = (
        select(Record)
        .where(Record.user_id == user_id)
        .where(Record.archived == archived)
        .order_by(_sql_desc(Record.id))
    )
    records = db.exec(smt).all()

    return [record.to_dict() for record in records]


# Route to get the status of an actual task
@record_bp.get("/by-session/{session_id}", response_model=RecordRead)
async def get_record_by_session(session_id: str, db: SessionDep):
    """Get a record by its session_id"""
    smt = select(Record).where(Record.session_id == session_id)
    record = db.exec(smt).one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


# Route to get the status of an actual task
@record_bp.get("/status/{task_id}")
async def transcription_status(task_id: int, db: SessionDep):

    task = db.get(Task, task_id)

    if not task:
        return {"error": "Task not found"}

    return {
        "task_id": task.id,
        "status": task.status,
        "result": task.result,
        "error": task.error,
    }


# CRUD Records
@record_bp.get("/record/{record_id}", response_model=RecordRead)
async def get_record(record_id: int, db: SessionDep):
    """Retrieves the information for the specific record"""
    record = db.get(Record, record_id)
    print(record)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@record_bp.delete("/record/{record_id}")
async def delete_record(record_id: int, db: SessionDep):
    """Delete a record permanently"""
    record = db.get(Record, record_id)
    if not record:
        return {"error": "Record not found"}

    audio_path = record.file if record.file else None

    db.delete(record)
    db.commit()

    if audio_path and os.path.exists(audio_path):
        try:
            os.remove(audio_path)
            logger.info(f"[DELETE] Audio file removed: {audio_path}")
        except OSError as e:
            logger.warning(f"[DELETE] Could not remove audio file {audio_path}: {e}")

    return {"status": "success", "message": "Record deleted"}


@record_bp.post("/record/{record_id}/summarize")
async def regenerate_summary(record_id: int, db: SessionDep):
    """Re-generate the LLM summary for an existing record using its current content."""
    record = db.get(Record, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if not record.content:
        raise HTTPException(
            status_code=400, detail="Record has no transcription content"
        )

    category_prompt = None
    category_llm_override = None
    if record.category_id:
        cat = db.get(Categories, record.category_id)
        if cat:
            category_prompt = cat.system_prompt
            if cat.llm_override_enabled and cat.llm_model:
                category_llm_override = cat

    llm_settings = db.exec(select(LlmSettingsModel)).first()

    def run_llm():
        text = record.content
        entity_mapping: dict[str, str] = {}

        if llm_settings and llm_settings.sanitizer_enabled and llm_settings.sanitizer_endpoint:
            text, entity_mapping = sanitize(
                text=text,
                endpoint=llm_settings.sanitizer_endpoint,
                api_key=llm_settings.sanitizer_api_key,
            )

        effective_prompt = (category_prompt or "") + (
            _PRESERVE_TOKENS_INSTRUCTION if entity_mapping else ""
        )

        if category_llm_override:
            model = OllamaModel(
                model_name=category_llm_override.llm_model,
                base_url=category_llm_override.llm_api_endpoint,
                api_key=category_llm_override.llm_api_key,
                temperature=category_llm_override.llm_temperature,
                max_tokens=category_llm_override.llm_max_tokens,
            )
        else:
            model = OllamaModel()

        result = model.generate_response(text, custom_system_prompt=effective_prompt or None)

        if entity_mapping:
            result = reinject(result, entity_mapping)

        return result, entity_mapping

    try:
        summary, entity_mapping = await asyncio.to_thread(run_llm)
        record.summarize = summary
        if entity_mapping:
            record.pii_mapping = json.dumps(entity_mapping, ensure_ascii=False)
        db.add(record)
        db.commit()
        db.refresh(record)
        return {"summarize": record.summarize}
    except Exception as e:
        logger.error(
            f"[SUMMARIZE] Error re-generating summary for record {record_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@record_bp.put("/record/{record_id}/archive")
async def archive_record(record_id: int, db: SessionDep):
    """Archive a record"""
    record = db.get(Record, record_id)
    if not record:
        return {"error": "Record not found"}

    record.archived = True
    db.add(record)
    db.commit()
    db.refresh(record)
    return record.to_dict()


@record_bp.put("/record/{record_id}/unarchive")
async def unarchive_record(record_id: int, db: SessionDep):
    """Unarchive a record"""
    record = db.get(Record, record_id)
    if not record:
        return {"error": "Record not found"}

    record.archived = False
    db.add(record)
    db.commit()
    db.refresh(record)
    return record.to_dict()
