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
import os
import shutil

# Third party
import uuid
from datetime import datetime

from fastapi import File, Form, HTTPException, UploadFile, WebSocket
from sqlalchemy import desc as _sql_desc
from sqlmodel import select

from backend.components.models.record_model import (
    Record,
    RecordCreate,
    RecordRead,
    RecordUpdate,
)
from backend.components.models.task_model import Task
from backend.components.modules.logger import get_logger
from backend.components.services.asr_factory import get_final_backend, get_live_backend
from backend.components.services.background_transcription_service import (
    background_transcription_task,
)
from backend.components.services.session_store import session_store
from backend.components.sql.sql_engine import SessionDep

# Custom imports
from backend.views.record_api import record_bp

logger = get_logger(__name__)


OUTPUT_DIR = "chunks"
os.makedirs(OUTPUT_DIR, exist_ok=True)


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

    # Register the active recording session in the store (Dict now, Redis later).
    # This is the single source of truth for an "unfinished recording".
    session_store.create_session(
        user_id=data.user_id,
        session_id=str(session_id),
        record_id=record.id,
        title=record.title,
        category_id=record.category_id,
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
    import glob

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

    # 2. Clean up audio files on disk for this session
    patterns = [
        f"{OUTPUT_DIR}/user{user_id}_session{session_id}_*_chunk.webm",
        f"{OUTPUT_DIR}/session_{user_id}_{session_id}_list.txt",
        f"{OUTPUT_DIR}/session_{session_id}_merged.webm",
    ]
    for pattern in patterns:
        for path in glob.glob(pattern):
            try:
                os.remove(path)
            except OSError as e:
                print(f"[CANCEL-CLEANUP-ERROR] {path}: {e}")

    # 3. Remove the live session from the store (Dict / Redis later)
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

    # Get the active recording session (live state lives in the store / Dict).
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
            )

    client_connected = True
    stopped = False

    # On resume: push the accumulated transcript back so the client gets it again.
    if session and session.get("live_text"):
        try:
            await websocket.send_json(
                {"session_id": session_id, "text": session["live_text"], "restored": True}
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

                if session is None:
                    continue

                # Buffer für finale Whisper-Transkription (im Store gehalten)
                session["audio_buffer"].extend(chunk)

                # Live ASR
                try:
                    backend = get_live_asr()

                    # chunk_length_s * 16000 samples/s * 4 bytes/sample (float32)
                    bytes_per_chunk = 3 * 16000 * 4  # default 3s chunks
                    bytes_per_overlap = 0
                    try:
                        from backend.components.services.settings_service import (
                            get_settings,
                        )

                        settings = get_settings()
                        bytes_per_chunk = settings.chunk_length_s * 16000 * 4
                        bytes_per_overlap = int(settings.overlap_s * 16000 * 4)
                    except Exception:
                        pass

                    buffer_len = len(session["audio_buffer"])
                    new_data_len = buffer_len - session["last_index"]

                    if new_data_len >= bytes_per_chunk:
                        # Extract slice of new audio data
                        start = session["last_index"]
                        end = start + bytes_per_chunk
                        audio_slice = bytes(session["audio_buffer"][start:end])
                        session["last_index"] = end - bytes_per_overlap

                        # Transcribe in background thread (non-blocking)
                        result_text = await asyncio.to_thread(
                            backend.transcribe,
                            audio=audio_slice,
                            language="de",
                            prompt=session["live_text"] or None,
                        )

                        if result_text:
                            session["live_text"] = (
                                session["live_text"] + " " + result_text
                            ).strip()

                            # Persist partial transcription to DB
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
                                    print(f"[WS-SEND-ERROR-PARTIAL] {e}")
                                    client_connected = False
                                    break

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
    # an unfinished recording so it can be resumed later. Nothing else to do.
    if not stopped:
        print(f"[WS] Session {session_id} left unfinished (kept for resume)")
        try:
            await websocket.close()
        except Exception:
            pass
        return

    # Stop event -> finalize the recording and run the transcription workflow.
    if session is not None:
        pcm_buffer = bytes(session["audio_buffer"])
        print(f"[FINAL-BUFFER] size={len(pcm_buffer)}")

        # Finished recording -> clear the live session from the store (Dict).
        session_store.delete_session(user_id_int)

        if len(pcm_buffer) == 0:
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

        # Socket schliessen (falls noch offen)
        try:
            if client_connected:
                await websocket.close()
        except Exception:
            pass  # Socket might be already closed

        # FFMPEG Merge Logic
        async def merge_and_process():
            import glob
            import subprocess

            # 1. Find all chunks for this session
            chunk_pattern = (
                f"{OUTPUT_DIR}/user{user_id}_session{session_id}_*_chunk.webm"
            )
            chunks = sorted(glob.glob(chunk_pattern))

            if not chunks:
                print(f"[ERROR] No chunks found for session {session_id}")
                background_transcription_task(task.id, session_id, pcm_buffer)
                return

            # 2. Create file list for ffmpeg
            list_file_path = f"{OUTPUT_DIR}/session_{user_id}_{session_id}_list.txt"
            with open(list_file_path, "w") as f:
                for chunk in chunks:
                    abs_path = os.path.abspath(chunk)
                    f.write(f"file '{abs_path}'\n")

            # 3. Merge
            output_filename = f"session_{session_id}_merged.webm"
            output_path = f"{OUTPUT_DIR}/{output_filename}"

            cmd = [
                "ffmpeg",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_file_path,
                "-c",
                "copy",
                "-y",
                output_path,
            ]

            print(f"[FFMPEG] Merging {len(chunks)} chunks...")
            try:
                process = await asyncio.to_thread(
                    subprocess.run, cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                if process.returncode != 0:
                    print(f"[FFMPEG-ERROR] {process.stderr.decode()}")
                    background_transcription_task(task.id, session_id, pcm_buffer)
                else:
                    print(f"[FFMPEG] Merge successful: {output_path}")
                    await asyncio.to_thread(
                        background_transcription_task,
                        task.id,
                        session_id,
                        None,
                        file_path=output_path,
                    )

            except Exception as e:
                print(f"[FFMPEG-EXCEPTION] {e}")
                background_transcription_task(task.id, session_id, pcm_buffer)

        # Background task starten (via helper to do ffmpeg first)
        asyncio.create_task(merge_and_process())

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
    """Upload audio chunk and append to session buffer"""
    actual_date = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Write into OUTPUT_DIR matching the merge glob in websocket_record.
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

    db.delete(record)
    db.commit()
    return {"status": "success", "message": "Record deleted"}


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
