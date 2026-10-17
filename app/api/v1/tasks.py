"""比价任务 HTTP 接口（TRD 第十三章）。"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from tradepilot.app.db.session import get_db
from tradepilot.app.schemas.task import TaskCreate, TaskList, TaskRead
from tradepilot.app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> TaskRead:
    return TaskService(db).create_task(payload)


@router.get("", response_model=TaskList)
def list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> TaskList:
    items, total = TaskService(db).list_tasks(skip=skip, limit=limit)
    return TaskList(total=total, items=items)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: uuid.UUID, db: Session = Depends(get_db)) -> TaskRead:
    return TaskService(db).get_task(task_id)
