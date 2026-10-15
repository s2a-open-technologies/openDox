"""openDox - Medical transcription platform
Copyright (C) 2025  S2A Open Technologies gGmbH
SPDX-FileCopyrightText: 2025 S2A Open Technologies gGmbH
SPDX-License-Identifier: AGPL-3.0-or-later

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

from datetime import datetime, timezone

from sqlmodel import select

from backend.components.models.task_model import Task
from backend.components.sql.sql_engine import Session


def update_task_status(db: Session, task_id: int, status: str, result=None, error=None):
    """Function to help updating the task status"""
    smt = select(Task).where(Task.id == task_id)
    task = db.exec(smt).one_or_none()

    if not task:
        return

    task.status = status
    task.updated_at = datetime.now(timezone.utc)

    if result is not None:
        task.result = result

    if error is not None:
        task.error = error

    db.add(task)
    db.commit()
    db.refresh(task)

    return task
