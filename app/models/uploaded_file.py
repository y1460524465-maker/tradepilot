"""上传文件模型（TRD 5.2：uploaded_files）。"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Enum, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FileTypeEnum(str, enum.Enum):
    XLSX = "xlsx"
    CSV = "csv"
    PDF = "pdf"


class FileStatus(str, enum.Enum):
    UPLOADED = "uploaded"          # 已上传，未解析
    PARSED = "parsed"              # 解析成功
    PARSE_FAILED = "parse_failed"  # 解析失败（记录原因，TRD 6.3）


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("comparison_tasks.id"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # 系统生成的存储路径，绝不使用用户文件名拼接（TRD 6.3）
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[FileTypeEnum] = mapped_column(
        Enum(FileTypeEnum, name="file_type", native_enum=False), nullable=False
    )
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[FileStatus] = mapped_column(
        Enum(FileStatus, name="file_status", native_enum=False),
        nullable=False,
        default=FileStatus.UPLOADED,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 解析预览：工作表/页结构、表头、前 N 行原始数据，用于追溯原始文件
    parsed_preview: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
