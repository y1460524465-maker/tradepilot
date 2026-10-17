"""报价提取相关接口模型。"""

import uuid

from pydantic import BaseModel


class FileExtractionSummary(BaseModel):
    file_id: uuid.UUID
    filename: str
    item_count: int
    skipped_rows: int
    warnings: list[str]


class ExtractSummaryRead(BaseModel):
    task_id: uuid.UUID
    total_items: int
    results: list[FileExtractionSummary]
