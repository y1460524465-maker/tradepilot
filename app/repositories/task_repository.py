"""比价任务的数据访问（TRD 4.3：数据访问层负责数据库读写）。"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tradepilot.app.models.comparison_task import ComparisonTask, TaskStatus


class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, task: ComparisonTask) -> ComparisonTask:
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get(self, task_id: uuid.UUID) -> ComparisonTask | None:
        return self.db.get(ComparisonTask, task_id)

    def list(self, skip: int = 0, limit: int = 50) -> tuple[list[ComparisonTask], int]:
        total = self.db.scalar(select(func.count()).select_from(ComparisonTask)) or 0
        stmt = (
            select(ComparisonTask)
            .order_by(ComparisonTask.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(stmt)), total

    def set_status(self, task_id: uuid.UUID, status: TaskStatus) -> ComparisonTask | None:
        task = self.get(task_id)
        if task is None:
            return None
        task.status = status
        self.db.commit()
        self.db.refresh(task)
        return task
