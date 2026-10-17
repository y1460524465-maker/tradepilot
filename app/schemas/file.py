"""文件相关接口的请求/响应模型（TRD 6.2 / 第十三章）。"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from tradepilot.app.models.uploaded_file import FileStatus, FileTypeEnum


class FileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    original_filename: str
    file_type: FileTypeEnum
    file_size: int
    status: FileStatus
    error_message: str | None = None
    created_at: datetime


class FileList(BaseModel):
    total: int
    items: list[FileRead]


class FileDetail(FileRead):
    """文件详情：含解析预览（工作表结构 / 表头 / 前 N 行），用于追溯原始文件。"""

    parsed_preview: dict | None = None


class FileParseResult(BaseModel):
    file_id: uuid.UUID
    filename: str
    status: FileStatus
    row_count: int | None = None
    error: str | None = None


class ParseSummary(BaseModel):
    task_id: uuid.UUID
    results: list[FileParseResult]
