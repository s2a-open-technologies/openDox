# Standard library
import os, shutil
from datetime import datetime
import subprocess
import random
import asyncio

# Third party
import uuid
import json
from fastapi import UploadFile, File, Form, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect
from sqlmodel import Session
import numpy as np
import soundfile as sf
from pydantic import BaseModel

# Custom imports
from app.views.record_api import record_bp
from app.components.modules.logger import get_logger
from app.components.services.final_transcription import Transcriber

from app.components.sql.sql_engine import SessionDep, get_session_factory
from app.components.models.record_model import (Record, RecordCreate, 
                                                RecordUpdate, RecordRead, 
                                                RecordChunk, FinalizeRecord)

from app.components.models.task_model import Task
from app.components.services.transcribe_service import background_transcription_task
from app.components.services.live_transcription import LiveASR

logger = get_logger(__name__)


record_ws_sessions = {}             # session_id → bytearray buffer
live_asr = LiveASR()                # Vosk

OUTPUT_DIR = 'chunks'
os.makedirs(OUTPUT_DIR, exist_ok=True)


@record_bp.post("/create")
async def record_create(
    db: SessionDep,
    data: RecordCreate
):
    """
    Creates a new record
    
    Parameters:
        payload (str): Payload with user_id and session_id and title
    """
    
    # Create a unique session_id
    session_id = uuid.uuid4()      
   
    # Creates a new record in database
    record = Record(
        session_id=str(session_id),
        user_id=data.user_id,
        title=data.title,
        timestamp=datetime.utcnow().isoformat(),
        content="",
        summarize="",
        file=""
    )
    
    db.add(record)
    db.commit()
    db.refresh(record)
    
    return record
    
@record_bp.websocket("/ws/record")
async def websocket_record(websocket: WebSocket, db: SessionDep):
    """Websocket for partial transcribing and saving into buffer"""

    await websocket.accept()

    session_id = websocket.query_params.get("session_id")
    user_id = websocket.query_params.get("user_id")

    if not session_id or not user_id:
        await websocket.send_json({"error": "session_id and user_id required"})
        await websocket.close()
        return

    print(f"[WS-START] user={user_id}, session={session_id}")

    record_ws_sessions[session_id] = bytearray()

    try:
        while True:
            msg = await websocket.receive()

            # Disconnect Message
            if msg["type"] == "websocket.disconnect":
                print(f"[WS-DISCONNECT] session={session_id}")
                break

            # Text Message
            if msg.get("text"):
                data = msg["text"]
                print(f"[WS-TEXT] {data}")

                # Stop event → beende die Aufnahme
                if "stop" in data:
                    print("[WS] Stop event received")
                    break

                continue  # andere Textnachrichten ignorieren

            # Binary Message
            if msg.get("bytes"):
                chunk = msg["bytes"]

                if not chunk:
                    print("[WARNING] Empty binary chunk received")
                    continue

                # Buffer für finale Whisper-Transkription
                record_ws_sessions[session_id].extend(chunk)

                # Live ASR mit Vosk
                try:
                    resp = live_asr.process(chunk)

                    if not resp:
                        continue

                    if "partial" in resp:
                        await websocket.send_json({
                            "session_id": session_id,
                            "partial": resp["partial"]
                        })

                    if "text" in resp:
                        await websocket.send_json({
                            "session_id": session_id,
                            "text": resp["text"]
                        })

                except Exception as e:
                    print(f"[LIVE-ASR-ERROR] {e}")

                continue  # nächster Loop

            # Ignoriere sonstige Nachrichtentypen
            print(f"[WS-UNKNOWN] {msg}")
            continue

    except Exception as e:
        print(f"[WS-ERROR] {e}")

    # =========================================================
    # FINAL PROCESSING — WIRD NUN IMMER AUSGEFÜHRT
    # =========================================================
    if session_id in record_ws_sessions:
        pcm_buffer = bytes(record_ws_sessions[session_id])
        print(f"[FINAL-BUFFER] size={len(pcm_buffer)}")
        del record_ws_sessions[session_id]

        if len(pcm_buffer) == 0:
            print("[WARNING] Empty audio buffer received")
            await websocket.send_json({
                "status": "error",
                "message": "No audio data received"
            })
            await websocket.close()
            return

        # Task in DB
        task = Task(status="pending")
        db.add(task)
        db.commit()
        db.refresh(task)

        # Signal an Client senden
        await websocket.send_json({
            "status": "finished",
            "task_id": task.id,
            "session_id": session_id
        })

        print("[WS] Background Whisper processing launched")

        await websocket.close()

        # Background task starten
        asyncio.create_task(
            asyncio.to_thread(background_transcription_task, task.id, pcm_buffer)
        )

    else:
        print("[ERROR] Session not found during final processing")
        await websocket.close()



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
