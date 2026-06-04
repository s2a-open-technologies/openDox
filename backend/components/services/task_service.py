from sqlmodel import select
from datetime import datetime

from backend.components.sql.sql_engine import Session
from backend.components.models.task_model import Task

def update_task_status(db: Session, task_id: int, status: str, result=None, error=None):
    """Function to help updating the task status"""    

    smt = select(Task).where(Task.id == task_id)
    task = db.exec(smt).one_or_none()
    
    if not task:
        return
    
    task.status = status
    task.updated_at = datetime.utcnow()
    
    if result is not None:
        task.result = result
    
    if error is not None:
        task.error = error
        
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return task
        