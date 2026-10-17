"""人工审核与导出 HTTP 接口（TRD 阶段七）。"""

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tradepilot.app.db.session import get_db
from tradepilot.app.services.export_service import ExportService, ReviewService

router = APIRouter(tags=["review"])


class ReviewConfirmRequest(BaseModel):
    item_ids: list[uuid.UUID] | None = None
    all: bool = False


class ReviewIssue(BaseModel):
    item_id: str
    issue: str


class ReviewSummary(BaseModel):
    total_items: int
    by_status: dict[str, int]
    pending_review: int
    issues: list[ReviewIssue]


class ReviewConfirmResponse(BaseModel):
    confirmed: int


@router.get("/tasks/{task_id}/review", response_model=ReviewSummary)
def review_summary(task_id: uuid.UUID, db: Session = Depends(get_db)) -> ReviewSummary:
    """任务审核概览：各状态计数与待处理问题清单。"""
    try:
        data = ReviewService(db).summary(task_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ReviewSummary(**data)


@router.post("/tasks/{task_id}/review/confirm", response_model=ReviewConfirmResponse)
def confirm_review(
    task_id: uuid.UUID, payload: ReviewConfirmRequest, db: Session = Depends(get_db)
) -> ReviewConfirmResponse:
    """批量确认报价明细（item_ids 或 all=true）。"""
    try:
        count = ReviewService(db).confirm(task_id, payload.item_ids, payload.all)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ReviewConfirmResponse(confirmed=count)


@router.get("/tasks/{task_id}/export")
def export_report(task_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    """导出比价报告 xlsx（比价结果 + 报价明细），导出后任务状态置 completed。"""
    try:
        filename, content = ExportService(db).export_xlsx(task_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
