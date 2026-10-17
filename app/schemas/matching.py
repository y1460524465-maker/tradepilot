"""匹配与比价的 HTTP 负载（TRD 第十三章：match / matches）。"""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from tradepilot.app.services.comparison_service import Comparability


class MatchRunSummary(BaseModel):
    """一次匹配运行的摘要。"""

    task_id: uuid.UUID
    total_items: int
    groups: dict[str, int]  # {"exact": n, "rule": n, "fuzzy": n, "single": n}


class ItemComparisonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: uuid.UUID
    supplier_name: str | None = None
    product_name: str | None = None
    model: str | None = None
    unit_price: Decimal | None = None
    currency: str | None = None
    quantity: Decimal | None = None
    estimated_total: Decimal | None = None
    rank: int | None = None
    diff_abs: Decimal | None = None
    diff_pct: Decimal | None = None
    issues: list[str] = []


class GroupComparisonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    match_id: uuid.UUID
    match_type: str
    match_status: str
    product_name: str | None = None
    model: str | None = None
    specification: str | None = None
    unit: str | None = None
    item_count: int
    comparability: Comparability
    reasons: list[str] = []
    note: str | None = None
    match_evidence: dict | None = None
    best_item_id: uuid.UUID | None = None
    items: list[ItemComparisonRead] = []


class ComparisonReport(BaseModel):
    task_id: uuid.UUID
    total_groups: int
    comparable_groups: int
    groups: list[GroupComparisonRead]


class MatchStatusUpdate(BaseModel):
    """人工确认/驳回可比组。"""

    match_status: str  # confirmed / pending_review
