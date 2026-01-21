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
        try:
            await websocket.send_json({"error": "session_id and user_id required"})
            await websocket.close()
        except:
            pass
        return

    print(f"[WS-START] user={user_id}, session={session_id}")
    
    record_ws_sessions[session_id] = bytearray()
    client_connected = True

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
                # print(f"[WS-TEXT] {data}")

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
                    
                    # Persist partial transcription to DB for resume capability
                    if result:
                        try:
                            record = db.exec(select(Record).where(Record.session_id == session_id)).one_or_none()
                            if record:
                                # Append new text with a space separator and timestamp
                                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                record.content = (record.content or "") + f" [{timestamp}] {result['text']}"
                                db.add(record)
                                db.commit()
                        except Exception as e:
                            print(f"[DB-PARTIAL-ERROR] {e}")

                    if result and client_connected:
                        try:
                            await websocket.send_json({
                                "session_id": session_id,
                                "text": result["text"]
                            })
                        except Exception as e:
                            print(f"[WS-SEND-ERROR-PARTIAL] {e}")
                            client_connected = False
                            break

                except Exception as e:
                    print(f"[LIVE-ASR-ERROR] {e}")

                continue  # nächster Loop

            # Ignoriere sonstige Nachrichtentypen
            print(f"[WS-UNKNOWN] {msg}")
            continue

    except Exception as e:
        print(f"[WS-ERROR] {e}")
        client_connected = False


    if session_id in record_ws_sessions:
        pcm_buffer = bytes(record_ws_sessions[session_id])
        print(f"[FINAL-BUFFER] size={len(pcm_buffer)}")
        del record_ws_sessions[session_id]

        if len(pcm_buffer) == 0:
            print("[WARNING] Empty audio buffer received")
            if client_connected:
                try:
                    await websocket.send_json({
                        "status": "error",
                        "message": "No audio data received"
                    })
                    await websocket.close()
                except:
                    pass
            return

        # Task in DB
        task = Task(status="pending")
        db.add(task)
        db.commit()
        db.refresh(task)

        if client_connected:
            try:
                await websocket.send_json({
                    "status": "finished",
                    "task_id": task.id,
                    "session_id": session_id
                })
                print("[WS] Background Whisper processing launched (Response sent)")
            except Exception as e:
                print(f"[WS-SEND-ERROR] Failed to send finish signal: {e}")
        else:
            print("[WS] Background Whisper processing launched (Client disconnected)")

        # Socket schließen (falls noch offen)
        try:
            if client_connected:
                await websocket.close()
        except Exception:
            pass # Socket might be already closed

        # FFMPEG Merge Logic
        async def merge_and_process():
            import subprocess, glob

            # 1. Find all chunks for this session
            # Pattern: user{user_id}_session{session_id}_*_chunk.webm
            chunk_pattern = f"{OUTPUT_DIR}/user{user_id}_session{session_id}_*_chunk.webm"
            chunks = sorted(glob.glob(chunk_pattern))

            if not chunks:
                 print(f"[ERROR] No chunks found for session {session_id}")
                 # Fallback to PCM buffer if needed, or fail.
                 # For now, we proceed with PCM buffer logic if no chunks (legacy behavior) 
                 # BUT user wants enable chunked upload flow.
                 # Let's assume chunks exist if upload worked.
                 background_transcription_task(task.id, session_id, pcm_buffer)
                 return

            # 2. Create file list for ffmpeg
            list_file_path = f"{OUTPUT_DIR}/session_{session_id}_list.txt"
            with open(list_file_path, "w") as f:
                for chunk in chunks:
                    # ffmpeg concat requires 'file path' format
                    # use absolute path to be safe or relative to directory
                    abs_path = os.path.abspath(chunk)
                    f.write(f"file '{abs_path}'\n")

            # 3. Merge
            output_filename = f"session_{session_id}_merged.webm"
            output_path = f"{OUTPUT_DIR}/{output_filename}"
            
            # Command: ffmpeg -f concat -safe 0 -i list.txt -c copy output.webm
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file_path,
                "-c", "copy",
                "-y", # Overwrite if exists
                output_path
            ]
            
            print(f"[FFMPEG] Merging {len(chunks)} chunks...")
            try:
                process = await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if process.returncode != 0:
                    print(f"[FFMPEG-ERROR] {process.stderr.decode()}")
                    # Fallback?
                    background_transcription_task(task.id, session_id, pcm_buffer)
                else:
                    print(f"[FFMPEG] Merge successful: {output_path}")
                    # Cleanup chunks and list file? (Optional, maybe keep for debug)
                    # os.remove(list_file_path)
                    # for c in chunks: os.remove(c)
                    
                    # 4. Trigger Background Task with FILE PATH
                    # We pass 'None' for pcm_buffer or handle it in service
                    await asyncio.to_thread(background_transcription_task, task.id, session_id, None, file_path=output_path)
            
            except Exception as e:
                print(f"[FFMPEG-EXCEPTION] {e}")
                background_transcription_task(task.id, session_id, pcm_buffer)

        # Background task starten (via helper to do ffmpeg first)
        asyncio.create_task(merge_and_process())

    else:
        print("[ERROR] Session not found during final processing")
        try:
           await websocket.close()
        except:
           pass
        
        
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
async def list_records(user_id: int, db: SessionDep, archived: bool = False):
    """List all records for a specific user, filtering by archived status"""
    
    # Get the record sessions per user and archived status
    smt = select(Record).where(Record.user_id == user_id).where(Record.archived == archived)
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
