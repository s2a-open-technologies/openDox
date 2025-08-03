
# Standard library
import os
from datetime import datetime
import asyncio
import time

# Third party
from fastapi import WebSocket, Request, WebSocketDisconnect
import numpy as np
import soundfile as sf

# Custom imports
from app.views.api import api_bp
from app.components.modules.logger import get_logger
from app.components.nodes.whisper_node import Transcriber

logger = get_logger(__name__)


OUTPUT_DIR = 'chunks'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Helper function for audio
async def save_pcm_to_float32(pcm_bytes: bytes, samplerate: int = 44100):
    print("Saving function entered")
    timestamp = int(time.time() * 1000)
    filename = os.path.join(OUTPUT_DIR, f"chunk_{timestamp}.wav")
    
    # Converting bytes to numpy array
    audio_arry = np.frombuffer(pcm_bytes, dtype=np.float32)
    
    # Save file
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None ,sf.write, filename, audio_arry, samplerate, 'FLOAT')
    
    return filename

# Websocket
@api_bp.websocket("/record")   
async def websocket_endpoint(websocket: WebSocket):
    """Function to accept websocket connection"""
    print("Funktion wird aufgerufen")
    
    await websocket.accept()
    print("Verbindung akzeptiert")
    
    transcriber = Transcriber()    
    
    try:
        # Whait for input and save to file
        while True:
            chunk = await websocket.receive_bytes()
            print(f"Chunk erhalten: {len(chunk)} Bytes")
            
            if len(chunk) < 4:
                print("Chunk zu klein")
                continue
            
            result = transcriber.transcribe(chunk)
            
            await websocket.send_text(result)
            
    except WebSocketDisconnect:
        print("Verbindung getrennt")
