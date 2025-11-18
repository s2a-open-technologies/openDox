from sqlmodel import select
from datetime import datetime

from app.components.sql.sql_engine import SessionDep
from app.components.models.task_model import Task


def update_task_status(db: SessionDep, task_id: int, status: str, result=None, error=None):
    """Function to help updating the task status"""

    task = db.query(Task).filter(Task.id == task_id).first()
    
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
        