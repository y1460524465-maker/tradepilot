"""报价明细与提取 HTTP 接口（TRD 第十三章：items / extract）。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.quotation_item import QuotationItem, ReviewStatus
from app.schemas.extraction import ExtractSummaryRead, FileExtractionSummary
from app.schemas.quotation import ItemList, QuotationItemRead, QuotationItemUpdate
from app.services.extraction_service import ExtractionService

router = APIRouter(tags=["items"])


@router.post("/tasks/{task_id}/extract", response_model=ExtractSummaryRead)
def extract_items(task_id: uuid.UUID, db: Session = Depends(get_db)) -> ExtractSummaryRead:
    """对任务内所有已解析文件执行表头映射与标准化，生成统一报价记录（幂等）。"""
    summary = ExtractionService(db).extract_task(task_id)
    return ExtractSummaryRead(
        task_id=task_id,
        total_items=sum(r.item_count for r in summary.results),
        results=[
            FileExtractionSummary(
                file_id=r.file_id,
                filename=r.filename,
                item_count=r.item_count,
                skipped_rows=r.skipped_rows,
                warnings=r.warnings[:50],
            )
            for r in summary.results
        ],
    )


@router.get("/tasks/{task_id}/items", response_model=ItemList)
def list_items(
    task_id: uuid.UUID,
    review_status: ReviewStatus | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> ItemList:
    stmt = select(QuotationItem).where(QuotationItem.task_id == task_id)
    count_stmt = (
        select(func.count()).select_from(QuotationItem).where(QuotationItem.task_id == task_id)
    )
    if review_status is not None:
        stmt = stmt.where(QuotationItem.review_status == review_status)
        count_stmt = count_stmt.where(QuotationItem.review_status == review_status)

    total = db.scalar(count_stmt) or 0
    items = db.scalars(
        stmt.order_by(QuotationItem.created_at.asc()).offset(skip).limit(limit)
    ).all()
    return ItemList(total=total, items=items)


@router.patch("/items/{item_id}", response_model=QuotationItemRead)
def update_item(
    item_id: uuid.UUID, payload: QuotationItemUpdate, db: Session = Depends(get_db)
) -> QuotationItemRead:
    """人工审核修正（TRD 第十一章）：只更新提供的字段。"""
    item = db.get(QuotationItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报价明细 {item_id} 不存在")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item
