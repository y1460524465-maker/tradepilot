"""比价任务接口的请求/响应模型（TRD 第十三章 /tasks 系列接口）。"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.comparison_task import TaskStatus


class TaskCreate(BaseModel):
    task_name: str = Field(..., min_length=1, max_length=200, description="比价任务名称")
    created_by: str | None = Field(None, max_length=100, description="创建人（认证上线前可填）")

    @field_validator("task_name")
    @classmethod
    def task_name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("任务名称不能为空白")
        return v


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_name: str
    status: TaskStatus
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class TaskList(BaseModel):
    total: int
    items: list[TaskRead]
