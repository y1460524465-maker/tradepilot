"""产品匹配模型（TRD 5.3 / 阶段五：product_matches）。

- 一个 match 记录代表一组"被认为是同一产品"的报价明细（可比组）。
- 铁律：规格冲突禁止自动合并；模糊匹配只作辅助证据，一律 pending_review。
- 比价计算不存本表，按 match 实时计算（确定性 Python + Decimal）。
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from tradepilot.app.db.base import Base


class MatchType(str, enum.Enum):
    """匹配方式（TRD 8.2：精确 → 规则 → 模糊仅作辅助）。"""

    EXACT = "exact"    # 型号+规格+单位完全一致，自动合并
    RULE = "rule"      # 规范化后产品名称+型号一致，且规格/单位无冲突，自动合并
    FUZZY = "fuzzy"    # 名称相似但有冲突或证据不足，仅提示，不自动合并
    SINGLE = "single"  # 没有找到可比对象，单独成组
    MANUAL = "manual"  # 人工指定归组


class MatchStatus(str, enum.Enum):
    """可比组状态：模糊/冲突组必须人工确认后才能参与正式比价。"""

    PENDING_REVIEW = "pending_review"
    CONFIRMED = "confirmed"


class ProductMatch(Base):
    __tablename__ = "product_matches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("comparison_tasks.id"), nullable=False, index=True
    )

    # 组的代表信息（取组内第一条的规范化值，便于列表展示）
    product_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    specification: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)

    match_type: Mapped[MatchType] = mapped_column(
        Enum(MatchType, name="match_type", native_enum=False), nullable=False
    )
    match_status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, name="match_status", native_enum=False),
        nullable=False,
        default=MatchStatus.PENDING_REVIEW,
    )
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 匹配证据：合并原因、相似度、冲突描述等（TRD 7.3 可解释性）
    match_evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
