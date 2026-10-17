"""报价明细模型（TRD 5.1 报价记录标准结构 / 5.2：quotation_items）。

- 金额/数量/税率用 Numeric（Decimal），不用二进制浮点（TRD 5.1 说明）。
- supplier_name / unit_price / currency 允许为空：提取缺失的行进入人工复核，
  而不是丢弃（TRD 第十章：缺少单价→阻止直接比价；缺少币种→提示确认）。
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExtractionMethod(str, enum.Enum):
    """提取方式（TRD 5.1 / 7.3，用于来源追溯）。"""

    RULE = "rule"      # 规则/结构化读取（表头映射等）
    AI = "ai"          # 大模型辅助提取
    MANUAL = "manual"  # 人工录入/人工修正


class ReviewStatus(str, enum.Enum):
    """审核状态（TRD 3.2 / 11：不确定的数据必须标记，不得静默放行）。"""

    PENDING_REVIEW = "pending_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class QuotationItem(Base):
    __tablename__ = "quotation_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("comparison_tasks.id"), nullable=False, index=True
    )
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("uploaded_files.id"), nullable=True, index=True
    )

    supplier_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    specification: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    shipping_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    moq: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(200), nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    # 来源追溯（TRD 7.3）：工作表、行号、原始表头映射等
    source_reference: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        Enum(ExtractionMethod, name="extraction_method", native_enum=False),
        nullable=False,
        default=ExtractionMethod.RULE,
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status", native_enum=False),
        nullable=False,
        default=ReviewStatus.PENDING_REVIEW,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
