from sqlmodel import select

from app.components.sql.sql_engine import get_session_factory
from app.components.models.task_model import Task
from app.components.models.record_model import RecordUpdate, Record
from app.components.services.task_service import update_task_status
from app.components.services.final_transcription import Transcriber
from app.components.modules.logger import get_logger
from app.components.llm.ollama_model import OllamaModel


logger = get_logger(__name__)


transcriber = Transcriber()  # Whisper lädt einmal global
session_factory = get_session_factory()
model = OllamaModel()

def background_transcription_task(task_id: int, session_id: str, pcm_buffer: bytes | None, file_path: str | None = None):
    db = session_factory()
    
    # Get the right record
    session = select(Record).where(Record.session_id == session_id)
    record = db.exec(session).one_or_none()
    
    try:
        # Update task status to running (transcribing)
        update_task_status(db, task_id,"transcribing")
        
        # Original text transcription
        if file_path:
             text = transcriber.transcribe(file_path)
        elif pcm_buffer:
             text = transcriber.transcribe(pcm_buffer)
        else:
             raise ValueError("No audio source provided (pcm_buffer or file_path)")  
        
        if record:
            record.content = text
            db.add(record)
            db.commit()
            db.refresh(record)
            logger.info(f"Transcription completed for session_id: {session_id}")
            with open("Transcription_test", "w") as file:
                file.write(text)        
        
        # Update task status to processing LLM
        update_task_status(db, task_id, "processing_llm")
        
        # Summarization using Ollama
        summary = model.generate_response(text)
        logger.info(f"Summarization completed for session_id: {session_id}")
        if record:
            record.summarize = summary
            db.add(record)
            db.commit()
            db.refresh(record)
            
        # Update task status to finished
        update_task_status(db, task_id, "finished")
            
    except Exception as e:
        update_task_status(db, task_id, "error", error=str(e))
        
    finally:
        db.close()
    

