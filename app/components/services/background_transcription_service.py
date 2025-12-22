from app.components.sql.sql_engine import get_session_factory
from app.components.models.task_model import Task
from app.components.services.task_service import update_task_status
from app.components.services.final_transcription import Transcriber

transcriber = Transcriber()  # Whisper lädt einmal global
session_factory = get_session_factory()

def background_transcription_task(task_id: int, pcm_buffer: bytes):
    db = session_factory()
    
    try:
        update_task_status(db, task_id,"running")
        text = transcriber.transcribe(pcm_buffer)
        with open("Transcription_test", "w") as file:
            file.write(text)
        update_task_status(db, task_id, "done", result=text)        
    except Exception as e:
        update_task_status(db, task_id, "error", error=str(e))
        
    finally:
        db.close()
    

