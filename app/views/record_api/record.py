# Standard library
import os, shutil
from datetime import datetime
import asyncio

# Third party
import uuid
from fastapi import UploadFile, File, Form, WebSocket
from sqlmodel import select

# Custom imports
from app.views.record_api import record_bp
from app.components.modules.logger import get_logger

from app.components.sql.sql_engine import SessionDep
from app.components.models.record_model import (Record, RecordCreate, 
                                                RecordUpdate, RecordRead, 
                                                RecordChunk, FinalizeRecord)

from app.components.models.task_model import Task
from app.components.services.background_transcription_service import background_transcription_task
from app.components.services.live_transcription_vosk import LiveASR
from app.components.services.live_transcription_whisper import WhisperLiveASR

logger = get_logger(__name__)


record_ws_sessions = {}             # session_id → bytearray buffer
#live_asr = LiveASR()               # Vosk

live_asr = WhisperLiveASR()         # Whisper


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
        timestamp=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        content="",
        summarize="",
        file=""
    )
    
    db.add(record)
    db.commit()
    db.refresh(record)
    
    return record
    
# Websocket Connection for live transcription
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
                    result = await asyncio.to_thread(live_asr.process, chunk)
                    
                    if result:
                        await websocket.send_json({
                            "session_id": session_id,
                            "text": result["text"]
                        })

                except Exception as e:
                    print(f"[LIVE-ASR-ERROR] {e}")

                continue  # nächster Loop

            # Ignoriere sonstige Nachrichtentypen
            print(f"[WS-UNKNOWN] {msg}")
            continue

    except Exception as e:
        print(f"[WS-ERROR] {e}")


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
            asyncio.to_thread(background_transcription_task, task.id, session_id, pcm_buffer)
        )

    else:
        print("[ERROR] Session not found during final processing")
        await websocket.close()
        
        
# Audiochunk upload
@record_bp.post("/record/upload-chunk")
async def record(db: SessionDep, file: UploadFile = File(...), user_id: int = Form(...), session_id: str = Form(...)):
    """Upload audio chunk and append to session buffer"""
    
    actual_date = datetime.now().strftime("%Y%m%d_%H%M%S")
    chunk_filename = f"{OUTPUT_DIR}/user{user_id}_session{session_id}_{actual_date}_chunk.webm"

    with open(f"{OUTPUT_DIR}/{chunk_filename}", "ab") as f:
        shutil.copyfileobj(file.file, f)
        
    return {"status": "chunk received"}


# Route for showing records in frontend
@record_bp.get("/record/list-records/{user_id}")
async def list_records(user_id: int, db: SessionDep):
    """List all records for a specific user"""
    
    print(f"TYPE: {type(user_id)}\nVALUE: {user_id}")
    
    # Get the record sessions per user
    smt = select(Record).where(Record.user_id == user_id)
    records = db.exec(smt).all()

    return [record.to_dict() for record in records]


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
