"""比价任务业务流程（TRD 4.3：业务服务层组织流程，API 层保持薄）。"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.comparison_task import ComparisonTask
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate


class TaskService:
    def __init__(self, db: Session):
        self.repo = TaskRepository(db)

    def create_task(self, payload: TaskCreate) -> ComparisonTask:
        task = ComparisonTask(
            task_name=payload.task_name.strip(),
            created_by=payload.created_by,
        )
        return self.repo.create(task)

    def get_task(self, task_id: uuid.UUID) -> ComparisonTask:
        task = self.repo.get(task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"任务 {task_id} 不存在",
            )
        return task

    def list_tasks(self, skip: int = 0, limit: int = 50) -> tuple[list[ComparisonTask], int]:
        limit = min(max(limit, 1), 200)
        return self.repo.list(skip=skip, limit=limit)
