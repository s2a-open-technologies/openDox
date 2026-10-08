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
import asyncio
import json
import os
import time

# Third party
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
from fastapi import Depends, File, Form, HTTPException, Response, UploadFile, WebSocket
from sqlalchemy import desc as _sql_desc
from sqlmodel import select

from backend.components.llm.llm_model import SummarizeModel
from backend.components.models.categories import Categories
from backend.components.models.llm_settings_model import LlmSettingsModel
from backend.components.models.record_model import (
    Record,
    RecordCreate,
    RecordRead,
    RecordUpdate,
)
from backend.components.models.task_model import Task
from backend.components.models.user_model import User
from backend.components.modules.api_errors import api_error
from backend.components.modules.audio import normalize_quiet_pcm
from backend.components.modules.logger import get_logger
from backend.components.modules.text_dedup import merge_overlapping_text
from backend.components.security.field_encryption import decrypt_bytes
from backend.components.security.hashing import decode_token
from backend.components.services import audio_storage
from backend.components.services.asr_backends.parakeet_stream import (
    ParakeetStreamBackend,
)
from backend.components.services.asr_factory import (
    get_final_backend,
    get_live_backend,
)
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
from backend.views.auth_api.dependencies import get_current_user

# Custom imports
from backend.views.record_api import record_bp

logger = get_logger(__name__)


def _require_owner(current_user: User, owner_id: int) -> None:
    """Raise 403 unless the current user owns the resource or is an admin.

    Args:
        current_user: Authenticated user making the request.
        owner_id: ``user_id`` of the resource being accessed.

    Raises:
        HTTPException: 403 if the user is neither the owner nor an admin.
    """
    if current_user.id != owner_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized for this resource")


async def _run_periodic_cleanup(session_id: str, websocket: WebSocket) -> None:
    """Smooth chunk-boundary punctuation in the live transcript via LLM.

    Non-blocking.
    """
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
async def record_create(
    db: SessionDep,
    data: RecordCreate,
    current_user: User = Depends(get_current_user),
):
    """Creates a new record

    Parameters:
        payload (str): Payload with user_id and session_id and title
    """
    _require_owner(current_user, data.user_id)

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


ALLOWED_AUDIO_EXTS = {
    "wav",
    "mp3",
    "m4a",
    "ogg",
    "flac",
    "webm",
    "aac",
    "opus",
}


def _ext_from_filename(filename: str | None) -> str:
    """Extract the lowercase extension from a filename, defaulting to 'wav'."""
    if filename and "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return "wav"


@record_bp.post("/upload")
async def upload_audio(
    db: SessionDep,
    file: UploadFile = File(...),
    category_id: int = Form(...),
    user_id: int = Form(...),
    title: str | None = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Upload a finished audio file and run it through the transcription pipeline.

    Accepts any ffmpeg-compatible audio format (validated by extension or
    content type). The file is saved to ``chunks/`` and processed by the
    existing ``background_transcription_task`` (Whisper -> PII -> LLM summary),
    identical to the live-recording finalize flow. No ``session_store`` entry
    is created — there is no live session to track.

    Args:
        db: Database session.
        file: Uploaded audio file.
        category_id: Category to associate with the record.
        user_id: Owner of the record.
        title: Optional title; defaults to ``"Upload {timestamp}"``.
        current_user: Authenticated user (must own ``user_id`` or be admin).

    Returns:
        Dict with ``task_id``, ``session_id`` and ``record_id``.

    Raises:
        HTTPException 415: If the file is not a supported audio format.
    """
    _require_owner(current_user, user_id)

    ext = _ext_from_filename(file.filename)
    content_type = (file.content_type or "").lower()
    if ext not in ALLOWED_AUDIO_EXTS and not content_type.startswith("audio/"):
        raise api_error(
            415,
            "unsupported_file_type",
            f"Unsupported file type '{ext}'. Allowed: "
            f"{', '.join(sorted(ALLOWED_AUDIO_EXTS))}",
            ext=ext,
            allowed=", ".join(sorted(ALLOWED_AUDIO_EXTS)),
        )

    session_id = str(uuid.uuid4())
    effective_title = title.strip() if title and title.strip() else None
    if not effective_title:
        effective_title = f"Upload {datetime.now().strftime('%d.%m.%Y %H:%M')}"

    record = Record(
        session_id=session_id,
        user_id=user_id,
        category_id=category_id,
        title=effective_title,
        timestamp=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        content="",
        summarize="",
        file="",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    task = Task(status="pending")
    db.add(task)
    db.commit()
    db.refresh(task)
    # Capture the plain id now, while `task` is still attached to this
    # request-scoped session — see the matching comment in the websocket
    # finalize() flow above for why touching `task.id` later (inside
    # run_pipeline(), a detached asyncio.create_task()) raises
    # "Instance <Task> is not bound to a Session".
    task_id = task.id
    record.task_id = task_id
    db.add(record)
    db.commit()

    upload_path = os.path.join(OUTPUT_DIR, f"upload_{session_id}.{ext}")
    try:
        with open(upload_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    except Exception as e:
        try:
            os.remove(upload_path)
        except OSError:
            pass
        db.delete(record)
        db.delete(task)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {e}")

    async def run_pipeline() -> None:
        """Run the background transcription task.

        ``background_transcription_task`` owns ``upload_path``'s fate itself —
        it deletes the file on success and moves it to a ``failed/`` dir for
        a manual retry on failure — so no cleanup is needed here.
        """
        try:
            await asyncio.to_thread(
                background_transcription_task,
                task_id,
                session_id,
                None,
                file_path=upload_path,
            )
        except Exception as e:
            logger.error("[UPLOAD] background_transcription_task failed: %s", e)

    asyncio.create_task(run_pipeline())

    return {
        "task_id": task_id,
        "session_id": session_id,
        "record_id": record.id,
    }


@record_bp.get("/active-session/{user_id}")
async def active_session(user_id: int, current_user: User = Depends(get_current_user)):
    """Return the user's active (unfinished) recording session, if any.

    Drives the "unfinished recording" indicator in the sidebar.
    """
    _require_owner(current_user, user_id)

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
async def cancel_session(
    user_id: int, db: SessionDep, current_user: User = Depends(get_current_user)
):
    """Cancel an unfinished recording.

    Deletes the live session from the store, the DB record and the audio files
    on disk for that session.
    """
    _require_owner(current_user, user_id)

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
    token = websocket.query_params.get("token")
    # live=0: the client has no live view (openDox client, live_view off) ->
    # record the audio only, skip every live ASR path (no Parakeet stream, no
    # chunked live transcription, no live cleanup). The final transcription
    # after "stop" reads the PCM file and is unaffected.
    live = websocket.query_params.get("live") != "0"

    if not session_id or not user_id or not token:
        try:
            await websocket.send_json(
                {"error": "session_id, user_id and token required"}
            )
            await websocket.close(code=1008)
        except Exception:
            pass
        return

    try:
        user_id_int = int(user_id)
    except ValueError:
        try:
            await websocket.send_json({"error": "user_id must be an integer"})
            await websocket.close(code=1008)
        except Exception:
            pass
        return

    payload = decode_token(token)
    if (
        not payload
        or payload.get("token_type") != "access"
        or payload.get("sub") is None
    ):
        try:
            await websocket.send_json({"error": "Invalid or expired token"})
            await websocket.close(code=1008)
        except Exception:
            pass
        return

    try:
        token_user_id = int(payload["sub"])
    except (TypeError, ValueError):
        token_user_id = None

    authed_user = db.get(User, token_user_id) if token_user_id is not None else None
    if (
        authed_user is None
        or not authed_user.is_active
        or (token_user_id != user_id_int and not authed_user.is_superuser)
    ):
        try:
            await websocket.send_json({"error": "Not authorized for this session"})
            await websocket.close(code=1008)
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

    # ── Streaming live ASR (Parakeet VAD-segmented) ──────────────────────
    # When the configured live backend supports streaming (Parakeet over WS),
    # we forward every PCM frame directly and relay partial/committed messages
    # back to the frontend, instead of the fixed-chunk + merge-overlap path.
    stream_session = None
    backend = None
    use_streaming = False
    if live:
        try:
            backend = get_live_asr()
            use_streaming = backend.supports_streaming()
        except Exception:
            backend = None
            use_streaming = False

    if use_streaming and isinstance(backend, ParakeetStreamBackend):
        # Callbacks update local_live_text via nonlocal and push to the client.
        async def _on_partial(partial_text: str) -> None:
            # A failed send here is transient (e.g. a brief proxy hiccup) —
            # it must NOT permanently disable the rest of the session. The
            # main loop's own "websocket.disconnect" check (below) is the
            # only place that should latch `client_connected` to False.
            if client_connected:
                try:
                    await websocket.send_json(
                        {"session_id": session_id, "partial": partial_text}
                    )
                except Exception as e:
                    print(f"[WS-SEND-ERROR] partial: {e}")

        async def _on_committed(committed: str, delta: str) -> None:
            nonlocal local_live_text
            local_live_text = committed
            session_store.set_live_state(session_id, local_last_index, committed)
            if client_connected and delta:
                try:
                    await websocket.send_json({"session_id": session_id, "text": delta})
                except Exception as e:
                    print(f"[WS-SEND-ERROR] committed: {e}")

        async def _on_final(final_text: str) -> None:
            nonlocal local_live_text
            local_live_text = final_text
            session_store.set_live_state(session_id, local_last_index, final_text)

        async def _on_error(e: Exception) -> None:
            nonlocal client_connected
            print(f"[STREAM-ASR-ERROR] {e}")
            client_connected = False

        stream_session = backend.open_session(
            on_partial=_on_partial,
            on_committed=_on_committed,
            on_final=_on_final,
            on_error=_on_error,
        )
        try:
            await stream_session.connect()
        except Exception as e:
            print(f"[STREAM-CONNECT-ERROR] {e}")
            stream_session = None

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

                # No live view requested: audio is on disk, nothing else to do.
                if not live:
                    continue

                # Streaming path: forward every PCM frame to the Parakeet
                # server's WS and let its VAD segment + decode. Partial /
                # committed messages are relayed to the client via the
                # callbacks set up above. Skip the fixed-chunk path entirely.
                if stream_session is not None:
                    try:
                        await stream_session.feed(chunk)
                    except Exception as e:
                        print(f"[STREAM-FEED-ERROR] {e}")
                    continue

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
                            bytes_per_left_context -= bytes_per_left_context % 4
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

                            if client_connected:
                                try:
                                    await websocket.send_json(
                                        {"session_id": session_id, "text": result_text}
                                    )
                                except Exception as e:
                                    print(f"[WS-SEND-ERROR] {e}")

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

    # Tear down the streaming ASR session if one is open. On a clean stop,
    # the Parakeet server's final transcript only feeds the live-typing UI
    # callbacks (moot once Stop is pressed) and finalize()/background
    # transcription below is fully independent of it — so don't make the
    # frontend's "finished" response wait on it. Run it as a detached task
    # instead, same pattern as finalize() further down. On a plain
    # disconnect we just close.
    if stream_session is not None:
        if stopped:

            async def _stop_stream_session():
                try:
                    await stream_session.stop(timeout=30.0)
                except Exception as e:
                    print(f"[STREAM-STOP-ERROR] {e}")

            asyncio.create_task(_stop_stream_session())
        else:
            await stream_session.close()

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
        # Capture the plain id now, while `task` is still attached to this
        # request-scoped session. `finalize()` below runs as a detached
        # background asyncio task via create_task() (not awaited), so by the
        # time it runs, this websocket handler may already have returned and
        # SessionDep's `with Session(engine)` block already closed `db` —
        # touching the (by-then expired-by-commit) `task.id` attribute at
        # that point raises "Instance <Task> is not bound to a Session".
        task_id = task.id

        # Link task to record
        record = db.exec(
            select(Record).where(Record.session_id == session_id)
        ).one_or_none()
        if record:
            record.task_id = task_id
            db.add(record)
            db.commit()

        if client_connected:
            try:
                await websocket.send_json(
                    {"status": "finished", "task_id": task_id, "session_id": session_id}
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
            """Convert PCM → WAV and launch background transcription.

            The PCM is always removed in the ``finally`` block — it's fully
            redundant once the WAV exists. The WAV's fate is NOT decided here
            anymore: ``background_transcription_task`` deletes it on success
            and moves it to a ``failed/`` dir for a manual retry on failure,
            so a crashed/failed transcription no longer loses the recording.
            """
            wav_path = os.path.splitext(pcm_path)[0] + ".wav"
            try:
                print(
                    f"[FINAL] Converting {pcm_path} ({audio_size // 1024} KB PCM) → WAV"
                )
                await asyncio.to_thread(_pcm_file_to_wav_file, pcm_path, wav_path)
                await asyncio.to_thread(
                    background_transcription_task,
                    task_id,
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


@record_bp.put("/record/{record_id}", response_model=RecordRead)
async def update_record(
    record_id: int,
    data: RecordUpdate,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Update an existing record (transcript, summary, title, category)"""
    record = db.get(Record, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    _require_owner(current_user, record.user_id)

    if data.title is not None:
        record.title = data.title
    if data.content is not None:
        record.content = data.content
    if data.summarize is not None:
        record.summarize = data.summarize
    if data.category_id is not None:
        if not db.get(Categories, data.category_id):
            raise api_error(404, "category_not_found", "Kategorie nicht gefunden")
        record.category_id = data.category_id

    db.add(record)
    db.commit()
    db.refresh(record)
    return RecordRead(
        id=record.id,
        session_id=record.session_id,
        user_id=record.user_id,
        category_id=record.category_id,
        title=record.title,
        content=record.content,
        summarize=record.summarize,
        timestamp=record.timestamp,
        has_audio=bool(record.file),
        archived=record.archived,
        task_id=record.task_id,
    )


# Route for showing records in frontend
@record_bp.get("/list-records/{user_id}")
async def list_records(
    user_id: int,
    db: SessionDep,
    archived: bool = False,
    current_user: User = Depends(get_current_user),
):
    """List all records for a specific user, filtering by archived status"""
    _require_owner(current_user, user_id)

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
async def get_record_by_session(
    session_id: str,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Get a record by its session_id"""
    smt = select(Record).where(Record.session_id == session_id)
    record = db.exec(smt).one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    _require_owner(current_user, record.user_id)
    return RecordRead(
        id=record.id,
        session_id=record.session_id,
        user_id=record.user_id,
        category_id=record.category_id,
        title=record.title,
        content=record.content,
        summarize=record.summarize,
        timestamp=record.timestamp,
        has_audio=bool(record.file),
        archived=record.archived,
        task_id=record.task_id,
    )


STALE_TASK_THRESHOLD_MINUTES = 7
_NON_TERMINAL_TASK_STATUSES = {"pending", "running", "transcribing", "processing_llm"}


# Route to get the status of an actual task
@record_bp.get("/status/{task_id}")
async def transcription_status(
    task_id: int, db: SessionDep, current_user: User = Depends(get_current_user)
):
    """Return the current status of a transcription task."""
    task = db.get(Task, task_id)

    if not task:
        return {"error": "Task not found"}

    if task.status in _NON_TERMINAL_TASK_STATUSES and datetime.now(
        timezone.utc
    ) - task.updated_at > timedelta(minutes=STALE_TASK_THRESHOLD_MINUTES):
        task.status = "error"
        task.error = "Zeitüberschreitung – keine Antwort vom Verarbeitungsprozess"
        db.add(task)
        db.commit()
        db.refresh(task)

    record = db.exec(select(Record).where(Record.task_id == task_id)).one_or_none()
    if record:
        _require_owner(current_user, record.user_id)
    elif not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized for this resource")

    return {
        "task_id": task.id,
        "status": task.status,
        "result": task.result,
        "error": task.error,
    }


def _require_admin(current_user: User) -> None:
    """Raise 403 unless the current user is an admin."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized for this resource")


@record_bp.get("/tasks/failed")
async def list_failed_tasks(
    db: SessionDep,
    current_user: User = Depends(get_current_user),
    offset: int = 0,
    limit: int = 100,
):
    """List failed transcription tasks that still have a retained audio file.

    Admin-only. Backs the "Fehlgeschlagene Transkriptionen" admin UI.
    """
    _require_admin(current_user)
    rows = db.exec(
        select(Task, Record)
        .join(Record, Record.task_id == Task.id)
        .where(Task.status == "error", Task.retry_audio_path.is_not(None))
        .order_by(_sql_desc(Task.updated_at))
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        {
            "task_id": task.id,
            "record_id": record.id,
            "title": record.title,
            "error": task.error,
            "updated_at": task.updated_at.isoformat(),
            "archived": task.retry_audio_in_s3,
        }
        for task, record in rows
    ]


@record_bp.post("/tasks/{task_id}/retry")
async def retry_failed_task(
    task_id: int, db: SessionDep, current_user: User = Depends(get_current_user)
):
    """Re-run the transcription pipeline on a failed task's retained audio.

    Admin-only. Fires the pipeline in the background and returns immediately,
    mirroring the ``finalize()``/``run_pipeline()`` fire-and-forget pattern.
    """
    _require_admin(current_user)

    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "error" or not task.retry_audio_path:
        raise api_error(
            409,
            "task_no_retry_audio",
            "Task hat keine zum Wiederholen vorgemerkte Audiodatei",
        )

    archived_key: str | None = None
    if task.retry_audio_in_s3:
        # Retained audio was archived to S3 (see failed_audio_archival_service.py)
        # after FAILED_AUDIO_RETENTION_DAYS — fetch it back to local disk so it
        # can run through the normal file_path-based transcription pipeline.
        encrypted = audio_storage.download_bytes(task.retry_audio_path)
        if encrypted is None:
            raise api_error(
                410,
                "archived_audio_gone",
                "Archivierte Audiodatei nicht mehr vorhanden",
            )
        ext = os.path.basename(task.retry_audio_path).split(".")[-2]
        os.makedirs("chunks/failed", exist_ok=True)
        retry_path = os.path.join("chunks", "failed", f"task_{task_id}.{ext}")
        with open(retry_path, "wb") as f:
            f.write(decrypt_bytes(encrypted))
        archived_key = task.retry_audio_path
    else:
        if not os.path.exists(task.retry_audio_path):
            raise api_error(
                410,
                "retained_audio_gone",
                "Aufbewahrte Audiodatei nicht mehr vorhanden",
            )
        retry_path = task.retry_audio_path

    record = db.exec(select(Record).where(Record.task_id == task_id)).one_or_none()
    if not record:
        raise api_error(
            404, "record_for_task_missing", "Zugehörige Aufnahme nicht gefunden"
        )

    task.status = "pending"
    task.error = None
    task.retry_audio_path = None
    task.retry_audio_in_s3 = False
    db.add(task)
    db.commit()

    # Only drop the S3 copy once the retry is durably queued (task.status
    # committed) — if the DB commit itself had failed, the archived copy
    # must stay in place rather than be lost.
    if archived_key:
        audio_storage.delete(archived_key)

    asyncio.create_task(
        asyncio.to_thread(
            background_transcription_task,
            task_id,
            record.session_id,
            None,
            file_path=retry_path,
        )
    )

    return {"task_id": task_id, "status": "pending"}


# CRUD Records
@record_bp.get("/record/{record_id}", response_model=RecordRead)
async def get_record(
    record_id: int, db: SessionDep, current_user: User = Depends(get_current_user)
):
    """Retrieves the information for the specific record"""
    record = db.get(Record, record_id)
    print(record)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    _require_owner(current_user, record.user_id)
    return RecordRead(
        id=record.id,
        session_id=record.session_id,
        user_id=record.user_id,
        category_id=record.category_id,
        title=record.title,
        content=record.content,
        summarize=record.summarize,
        timestamp=record.timestamp,
        has_audio=bool(record.file),
        archived=record.archived,
        task_id=record.task_id,
    )


@record_bp.delete("/record/{record_id}")
async def delete_record(
    record_id: int, db: SessionDep, current_user: User = Depends(get_current_user)
):
    """Delete a record permanently"""
    from backend.components.services import audio_storage

    record = db.get(Record, record_id)
    if not record:
        return {"error": "Record not found"}
    _require_owner(current_user, record.user_id)

    audio_key = record.file if record.file else None

    db.delete(record)
    db.commit()

    if audio_key:
        audio_storage.delete(audio_key)
        logger.info(f"[DELETE] Audio object removed: {audio_key}")

    return {"status": "success", "message": "Record deleted"}


@record_bp.post("/record/{record_id}/summarize")
async def regenerate_summary(
    record_id: int, db: SessionDep, current_user: User = Depends(get_current_user)
):
    """Re-generate the LLM summary for an existing record using its current content."""
    record = db.get(Record, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    _require_owner(current_user, record.user_id)
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

        if (
            llm_settings
            and llm_settings.sanitizer_enabled
            and llm_settings.sanitizer_endpoint
        ):
            text, entity_mapping = sanitize(
                text=text,
                endpoint=llm_settings.sanitizer_endpoint,
                api_key=llm_settings.sanitizer_api_key,
            )

        effective_prompt = (category_prompt or "") + (
            _PRESERVE_TOKENS_INSTRUCTION if entity_mapping else ""
        )

        if category_llm_override:
            model = SummarizeModel(
                model_name=category_llm_override.llm_model,
                base_url=category_llm_override.llm_api_endpoint,
                api_key=category_llm_override.llm_api_key,
                temperature=category_llm_override.llm_temperature,
                max_tokens=category_llm_override.llm_max_tokens,
                top_p=category_llm_override.llm_top_p,
                frequency_penalty=category_llm_override.llm_frequency_penalty,
                enable_thinking=category_llm_override.llm_enable_thinking,
            )
        else:
            model = SummarizeModel()

        result = model.generate_response(
            text, custom_system_prompt=effective_prompt or None
        )

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
async def archive_record(
    record_id: int, db: SessionDep, current_user: User = Depends(get_current_user)
):
    """Archive a record"""
    record = db.get(Record, record_id)
    if not record:
        return {"error": "Record not found"}
    _require_owner(current_user, record.user_id)

    record.archived = True
    db.add(record)
    db.commit()
    db.refresh(record)
    return record.to_dict()


@record_bp.put("/record/{record_id}/unarchive")
async def unarchive_record(
    record_id: int, db: SessionDep, current_user: User = Depends(get_current_user)
):
    """Unarchive a record"""
    record = db.get(Record, record_id)
    if not record:
        return {"error": "Record not found"}
    _require_owner(current_user, record.user_id)

    record.archived = False
    db.add(record)
    db.commit()
    db.refresh(record)
    return record.to_dict()


_AUDIO_MEDIA_TYPES = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "flac": "audio/flac",
    "ogg": "audio/ogg",
}


@record_bp.get("/record/{record_id}/audio")
async def download_audio(
    record_id: int, db: SessionDep, current_user: User = Depends(get_current_user)
):
    """Download the persisted audio for a record.

    The caller must be authenticated and own the record (or be an admin).
    The audio is fetched from S3, decrypted, and streamed back — it is never
    written to local disk.

    Returns:
        The decrypted audio bytes with a Content-Disposition header. Format
        (mp3/wav/flac/ogg) is derived from the S3 key's extension
        (``records/{id}.{ext}.enc``), since it's configurable and may differ
        between recordings made under different admin settings over time.
        404 if no audio is associated with the record.
    """
    from backend.components.security.field_encryption import decrypt_bytes
    from backend.components.services import audio_storage
    from backend.components.services.background_transcription_service import (
        _sanitize_filename,
    )

    record = db.get(Record, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    _require_owner(current_user, record.user_id)

    if not record.file:
        raise api_error(
            404,
            "no_audio_for_record",
            "Keine Audiodatei für diese Aufnahme vorhanden",
        )

    encrypted = audio_storage.download_bytes(record.file)
    if encrypted is None:
        raise api_error(
            404,
            "no_audio_for_record",
            "Keine Audiodatei für diese Aufnahme vorhanden",
        )

    # record.file is "records/{id}.{ext}.enc" — the middle segment is the format.
    ext = record.file.rsplit(".", 2)[-2] if record.file.count(".") >= 2 else "mp3"
    media_type = _AUDIO_MEDIA_TYPES.get(ext, "audio/mpeg")
    ext = ext if ext in _AUDIO_MEDIA_TYPES else "mp3"

    plaintext = decrypt_bytes(encrypted)
    filename = f"{_sanitize_filename(record.title)}.{ext}"
    return Response(
        content=plaintext,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
