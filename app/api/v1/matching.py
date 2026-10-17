"""匹配与比价 HTTP 接口（TRD 第十三章）。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tradepilot.app.db.session import get_db
from tradepilot.app.models.comparison_task import ComparisonTask
from tradepilot.app.models.product_match import MatchStatus, ProductMatch
from tradepilot.app.models.quotation_item import QuotationItem
from tradepilot.app.schemas.matching import (
    ComparisonReport,
    GroupComparisonRead,
    MatchRunSummary,
    MatchStatusUpdate,
)
from tradepilot.app.services.comparison_service import Comparability, compute_group, compute_task
from tradepilot.app.services.matching_service import MatchingService

router = APIRouter(tags=["matching"])


def _ensure_task(db: Session, task_id: uuid.UUID) -> None:
    if db.get(ComparisonTask, task_id) is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")


@router.post("/tasks/{task_id}/match", response_model=MatchRunSummary)
def run_match(task_id: uuid.UUID, db: Session = Depends(get_db)) -> MatchRunSummary:
    """对任务内全部报价明细执行产品匹配（幂等，重跑会重建分组）。"""
    _ensure_task(db, task_id)
    counts = MatchingService(db).run_match(task_id)
    total_items = db.scalar(
        select(func.coalesce(func.sum(ProductMatch.item_count), 0)).where(
            ProductMatch.task_id == task_id
        )
    )
    return MatchRunSummary(task_id=task_id, total_items=int(total_items), groups=counts)


@router.get("/tasks/{task_id}/matches", response_model=ComparisonReport)
def get_comparison(task_id: uuid.UUID, db: Session = Depends(get_db)) -> ComparisonReport:
    """任务内全部可比组的比价结果（含可比性检查与价格排名）。"""
    _ensure_task(db, task_id)
    groups = compute_task(db, task_id)
    return ComparisonReport(
        task_id=task_id,
        total_groups=len(groups),
        comparable_groups=sum(1 for g in groups if g.comparability == Comparability.COMPARABLE),
        groups=[GroupComparisonRead.model_validate(g, from_attributes=True) for g in groups],
    )


@router.patch("/matches/{match_id}", response_model=GroupComparisonRead)
def update_match_status(
    match_id: uuid.UUID, payload: MatchStatusUpdate, db: Session = Depends(get_db)
) -> GroupComparisonRead:
    """人工确认/打回可比组（模糊匹配组必须确认后才可采信比价结果）。"""
    group = db.get(ProductMatch, match_id)
    if group is None:
        raise HTTPException(status_code=404, detail=f"可比组 {match_id} 不存在")
    try:
        group.match_status = MatchStatus(payload.match_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="match_status 只能是 confirmed 或 pending_review",
        )
    db.commit()
    db.refresh(group)
    items = (
        db.query(QuotationItem)
        .filter(QuotationItem.match_id == group.id)
        .order_by(QuotationItem.created_at.asc())
        .all()
    )
    return GroupComparisonRead.model_validate(compute_group(group, items), from_attributes=True)
