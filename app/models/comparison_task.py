"""比价任务模型（TRD 5.2：comparison_tasks）。"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TaskStatus(str, enum.Enum):
    """任务状态（TRD F10：上传、解析、待审核、已完成等）。"""

    CREATED = "created"                # 已创建，待上传文件
    PROCESSING = "processing"          # 解析/匹配/比价处理中
    PENDING_REVIEW = "pending_review"  # 待人工审核
    COMPLETED = "completed"            # 已确认完成
    FAILED = "failed"                  # 处理失败（可查看原因）


class ComparisonTask(Base):
    __tablename__ = "comparison_tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", native_enum=False),
        nullable=False,
        default=TaskStatus.CREATED,
    )
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
