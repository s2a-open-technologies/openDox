
# Standard library
import os, shutil
from datetime import datetime
import asyncio
import time
import subprocess

# Third party
from fastapi import UploadFile, File, Form
import numpy as np
import soundfile as sf
from pydantic import BaseModel


# Custom imports
from app.views.api import api_bp
from app.components.modules.logger import get_logger
from app.components.nodes.whisper_node import Transcriber

logger = get_logger(__name__)

class FinalizeRecord(BaseModel):
    session_id: str


OUTPUT_DIR = 'chunks'
os.makedirs(OUTPUT_DIR, exist_ok=True)

@api_bp.post("/record")
async def record(file: UploadFile = File(...), session_id: str = Form(...)):
    """
    Record a new audio file and save it to the server.

    Parameters:
        file (UploadFile): The uploaded audio file.
        session_id (str): A unique identifier for the recording session.

    Returns:
        dict: A dictionary containing information about the recorded file, including its path and duration.
    """
    filepath = os.path.join(OUTPUT_DIR, f"{session_id}.webm")
    
    with open(filepath, "ab") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"status": "chunk_received", "session_id": session_id}, 200


@api_bp.post("/record_finalize")
async def record_finalize(req: FinalizeRecord):
    webm_path = os.path.join(OUTPUT_DIR, f"{req.session_id}.webm")
    wav_path = os.path.join(OUTPUT_DIR, f"{req.session_id}.wav")
           
    if not os.path.exists(webm_path):    
        return {"status": "error", "detail": "file not found"}, 422
    
    subprocess.run([
        "app/components/ffmpeg/bin/ffmpeg",
        "-y", "-i", webm_path,
        "-ac", "1", "-ar", "16000",
        wav_path], check=True)
    
    # Transcriben
    
    transcriber = Transcriber()
    with open(wav_path, 'rb') as file:
        pcm_buffer = file.read()
        
    transcription = transcriber.transcribe(pcm_buffer=pcm_buffer)
    
    with open("transcription.txt", "a") as file:
        file.write(transcription)
    
    return {"status": "finalized", "file": webm_path, "transcription": transcription}, 200    
