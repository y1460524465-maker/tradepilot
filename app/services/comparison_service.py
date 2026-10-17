"""比价计算（TRD 8.3 / 阶段五：可比性检查 + 价格计算）。

铁律：全部计算由确定性 Python 代码 + Decimal 完成，任何 AI 不得参与算钱。
可比性规则（TRD 第十章）：
- 缺少单价 → 阻止该条直接比价；
- 组内币种不一致 → 不可直接比较（MVP 不做汇率换算）；
- 单位/规格不一致 → 可比性告警，需人工确认；
- 模糊匹配组（pending_review）→ 结果仅供参考。
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product_match import MatchStatus, ProductMatch
from app.models.quotation_item import QuotationItem

_PCT = Decimal("0.01")  # 百分比保留 2 位


class Comparability(str, Enum):
    COMPARABLE = "comparable"            # 可直接比价
    NEEDS_REVIEW = "needs_review"        # 有告警，人工确认后比价
    NOT_COMPARABLE = "not_comparable"    # 不可直接比较


@dataclass
class ItemComparison:
    item_id: uuid.UUID
    supplier_name: str | None
    product_name: str | None
    model: str | None
    unit_price: Decimal | None
    currency: str | None
    quantity: Decimal | None
    estimated_total: Decimal | None = None
    rank: int | None = None          # 组内价格排名（1 = 最低价）
    diff_abs: Decimal | None = None  # 与最低价差额
    diff_pct: Decimal | None = None  # 与最低价相对差（%）
    issues: list[str] = field(default_factory=list)


@dataclass
class GroupComparison:
    match_id: uuid.UUID
    match_type: str
    match_status: str
    product_name: str | None
    model: str | None
    specification: str | None
    unit: str | None
    item_count: int
    comparability: Comparability
    reasons: list[str] = field(default_factory=list)
    note: str | None = None
    match_evidence: dict | None = None
    best_item_id: uuid.UUID | None = None
    items: list[ItemComparison] = field(default_factory=list)


def compute_group(group: ProductMatch, items: list[QuotationItem]) -> GroupComparison:
    """对一个可比组执行可比性检查与价格计算（纯函数式，无副作用）。"""
    result = GroupComparison(
        match_id=group.id,
        match_type=group.match_type.value if hasattr(group.match_type, "value") else str(group.match_type),
        match_status=group.match_status.value if hasattr(group.match_status, "value") else str(group.match_status),
        product_name=group.product_name,
        model=group.model,
        specification=group.specification,
        unit=group.unit,
        item_count=len(items),
        comparability=Comparability.COMPARABLE,
        note=group.note,
        match_evidence=group.match_evidence,
    )

    comparisons = [
        ItemComparison(
            item_id=it.id,
            supplier_name=it.supplier_name,
            product_name=it.product_name,
            model=it.model,
            unit_price=it.unit_price,
            currency=it.currency,
            quantity=it.quantity,
        )
        for it in items
    ]

    # ---- 逐条问题检查
    for c in comparisons:
        if c.unit_price is None:
            c.issues.append("缺少单价，阻止直接比价")
        if c.currency is None:
            c.issues.append("缺少币种，需人工确认")

    # ---- 组内一致性检查
    currencies = {c.currency for c in comparisons if c.currency}
    if len(currencies) > 1:
        result.comparability = Comparability.NOT_COMPARABLE
        result.reasons.append(f"币种不一致（{'、'.join(sorted(currencies))}），MVP 不做汇率换算")
    units = {_norm(it.unit) for it in items if _norm(it.unit)}
    if len(units) > 1:
        result.reasons.append(f"计量单位不一致（{'、'.join(sorted(units))}），确认后可比")
        if result.comparability == Comparability.COMPARABLE:
            result.comparability = Comparability.NEEDS_REVIEW
    specs = {_norm(it.specification) for it in items if _norm(it.specification)}
    if len(specs) > 1:
        result.reasons.append("组内规格表述不一致，请人工核对是否同一产品")
        if result.comparability == Comparability.COMPARABLE:
            result.comparability = Comparability.NEEDS_REVIEW
    if group.match_status == MatchStatus.PENDING_REVIEW and group.match_type.value == "fuzzy":
        result.comparability = Comparability.NEEDS_REVIEW
        result.reasons.append("模糊匹配组，需人工确认同一性后才能采信比价结果")

    # ---- 价格排名（只对"有单价且币种与组一致"的条目）
    dominant_currency = _dominant(currencies)
    priceable = [
        c for c in comparisons if c.unit_price is not None and c.currency == dominant_currency
    ]
    priceable.sort(key=lambda c: c.unit_price)
    if priceable:
        lowest = priceable[0].unit_price
        for rank, c in enumerate(priceable, start=1):
            c.rank = rank
            c.diff_abs = (c.unit_price - lowest).quantize(Decimal("0.000001"))
            if lowest > 0:
                pct = (c.unit_price - lowest) / lowest * 100
                c.diff_pct = pct.quantize(_PCT, rounding=ROUND_HALF_UP)
            if c.quantity is not None:
                c.estimated_total = (c.unit_price * c.quantity).quantize(Decimal("0.01"))
        result.best_item_id = priceable[0].item_id

    if len(priceable) < 2:
        result.comparability = Comparability.NOT_COMPARABLE
        result.reasons.append("有效报价比价对象不足 2 条（缺单价或币种不一致）")

    result.items = comparisons
    return result


def _norm(value: str | None) -> str | None:
    from app.services.matching_service import norm_identity

    return norm_identity(value)


def _dominant(currencies: set[str]) -> str | None:
    """组内唯一币种；多个时返回 None（阻止排名，币种不一致已标记不可比）。"""
    return next(iter(currencies)) if len(currencies) == 1 else None


def compute_task(db: Session, task_id: uuid.UUID) -> list[GroupComparison]:
    """计算一个任务内全部可比组的比价结果。"""
    groups = db.scalars(
        select(ProductMatch)
        .where(ProductMatch.task_id == task_id)
        .order_by(ProductMatch.created_at.asc())
    ).all()
    if not groups:
        return []
    items = db.scalars(
        select(QuotationItem)
        .where(QuotationItem.task_id == task_id, QuotationItem.match_id.is_not(None))
        .order_by(QuotationItem.created_at.asc())
    ).all()
    by_match: dict[uuid.UUID, list[QuotationItem]] = {}
    for it in items:
        by_match.setdefault(it.match_id, []).append(it)
    return [compute_group(g, by_match.get(g.id, [])) for g in groups]
