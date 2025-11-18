from app.components.sql.sql_engine import get_session_factory
from app.components.models.task_model import Task
from app.components.services.task_service import update_task
from app.components.nodes.transcribe_node import Transcriber

transcriber = Transcriber()  # Whisper lädt einmal global

def background_transcription_task(task_id: int, pcm_buffer: bytes, get_session_factory):
    db = get_session_factory()
    
    try:
        update_task(db, task_id,"running")
        text = transcriber.transcribe(pcm_buffer)
        update_task(db, task_id, "done", result=text)        
    except Exception as e:
        update_task(db, task_id, "error", error=str(e))
        
    finally:
        db.close()
    
