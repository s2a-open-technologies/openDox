"""
  openDox - Medical transcription platform
  Copyright (C) 2025  crizz <christopher.abanilla@gmx.de>

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU Affero General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU Affero General Public License for more details.

  You should have received a copy of the GNU Affero General Public License
  along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

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
        