"""AI 辅助提取 HTTP 接口（TRD 第九章）。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.ai_extraction_service import AIExtractionService
from app.db.session import get_db
from app.models.comparison_task import ComparisonTask
from app.schemas.extraction import ExtractSummaryRead, FileExtractionSummary

router = APIRouter(tags=["ai"])


@router.post("/tasks/{task_id}/ai_extract", response_model=ExtractSummaryRead)
def ai_extract(task_id: uuid.UUID, db: Session = Depends(get_db)) -> ExtractSummaryRead:
    """对规则提取没有产出的文件执行大模型辅助提取（需显式启用 AI）。"""
    if db.get(ComparisonTask, task_id) is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    try:
        summary = AIExtractionService(db).extract_task(task_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return ExtractSummaryRead(
        task_id=task_id,
        total_items=summary.total_items,
        results=[
            FileExtractionSummary(
                file_id=f["file_id"],
                filename=f["filename"],
                item_count=f["item_count"],
                skipped_rows=0,
                warnings=f["errors"][:20],
            )
            for f in summary.files
        ],
    )
