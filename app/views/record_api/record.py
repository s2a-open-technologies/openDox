
# Standard library
import os, shutil
from datetime import datetime
import subprocess

# Third party
import uuid
from fastapi import UploadFile, File, Form, Depends, BackgroundTasks
from sqlmodel import Session
import numpy as np
import soundfile as sf
from pydantic import BaseModel


# Custom imports
from app.views.record_api import record_bp
from app.components.modules.logger import get_logger
from app.components.nodes.transcribe_node import Transcriber

from app.components.sql.sql_engine import SessionDep, get_session_factory
from app.components.models.record_model import (Record, RecordCreate, 
                                                RecordUpdate, RecordRead, 
                                                RecordChunk, FinalizeRecord)

from app.components.models.task_model import Task
from app.components.services.transcribe_service import background_transcription_task

logger = get_logger(__name__)



OUTPUT_DIR = 'chunks'
os.makedirs(OUTPUT_DIR, exist_ok=True)

@record_bp.post("/record/create")
async def record_create(
    db: SessionDep,
    payload: str = Form(...)):
    """
    Creates a new record
    
    Parameters:
        payload (str): Payload with user_id and session_id and title
    """
    
    # Create a unique session_id
    session_id = uuid.uuid4()
    
    # Creating the database record
    data = RecordCreate.model_validate_json(payload)  
    
    # Creates a new record in database
    record = Record(
        session_id=session_id,
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


@record_bp.post("/record")
async def record(
    db: SessionDep,
    file: UploadFile = File(...),
    payload: str = Form(...)):
    
    data = RecordChunk.model_validate_json(payload)

    # Save the uploaded file to a temporary directory
    temp_file_path = os.path.join(OUTPUT_DIR, f"{data.session_id}.wav")
    with open(temp_file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Transcribe the audio file using Whisper
    transcriber = Transcriber()
    transcription = transcriber.transcribe(temp_file_path)

    # Create a new record in database
    record = Record(
        session_id=data.session_id,
        user_id=data.user_id,
        title="",
        timestamp=datetime.utcnow().isoformat(),
        content="",
        summarize="",
        file=temp_file_path
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record

    
@record_bp.post("/record_finalize")
async def record_finalize(
    background_tasks: BackgroundTasks,
    req: FinalizeRecord, 
    db: SessionDep
    ):
    webm_path = os.path.join(OUTPUT_DIR, f"{req.user_id}_{req.session_id}.webm")
    wav_path = os.path.join(OUTPUT_DIR, f"{req.user_id}_{req.session_id}.wav")
           
    if not os.path.exists(webm_path):    
        return {"status": "error", "detail": "file not found"}, 422
    
    subprocess.run([
        "app/components/ffmpeg/bin/ffmpeg",
        "-y", "-i", webm_path,
        "-ac", "1", "-ar", "16000",
        wav_path], check=True)
    
    # Transcriben        
    with open(wav_path, 'rb') as file:
        pcm_buffer = file.read()
        
        # Task erstellen
        task = Task(status="pending")
        db.add(task)
        db.commit()
        db.refresh(task)

        # Worker starten
        background_tasks.add_task(
            background_transcription_task,
            task_id=task.id,
            pcm_buffer=pcm_buffer,
            db_session_factory=get_session_factory
        )

    return {"task_id": task.id, "status": task.status}   


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