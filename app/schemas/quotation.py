"""报价记录标准结构（TRD 5.1）。

- 金额、数量、税率等计算字段一律使用 Decimal，禁止二进制浮点数直接参与财务计算。
- 未从文件中提取到的字段保持 None，由上层流程进入人工复核，不做猜测填充（TRD 7.3）。
"""

from datetime import date
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from tradepilot.app.models.quotation_item import ExtractionMethod, ReviewStatus


class CurrencyCode(str, Enum):
    """第一版常用币种；后续按贸易场景扩展。"""

    CNY = "CNY"
    USD = "USD"
    EUR = "EUR"
    JPY = "JPY"
    HKD = "HKD"


class QuotationItemBase(BaseModel):
    """报价明细的统一结构（人工录入契约：必需字段缺失直接校验失败）。"""

    supplier_name: str = Field(..., min_length=1, description="供应商名称")
    product_name: str = Field(..., min_length=1, description="产品名称")
    model: str | None = Field(None, description="产品型号")
    specification: str | None = Field(None, description="产品规格")
    quantity: Decimal | None = Field(None, gt=0, description="报价数量")
    unit: str | None = Field(None, description="计量单位")
    unit_price: Decimal = Field(..., gt=0, description="报价单价")
    currency: CurrencyCode = Field(..., description="币种")
    tax_rate: Decimal | None = Field(None, ge=0, le=1, description="税率（0~1）")
    shipping_cost: Decimal | None = Field(None, ge=0, description="运费")
    moq: Decimal | None = Field(None, ge=0, description="最小起订量")
    lead_time_days: int | None = Field(None, ge=0, description="交货周期（天）")
    payment_terms: str | None = Field(None, description="付款条件")
    valid_until: date | None = Field(None, description="报价有效期")


class QuotationItemCreate(QuotationItemBase):
    """人工录入/修正报价明细时的负载。"""

    extraction_method: ExtractionMethod = ExtractionMethod.RULE
    source_file_id: UUID | None = Field(None, description="来源文件 ID")
    source_reference: dict | None = Field(
        None, description="来源追溯：工作表、页码、行号、原始文本片段等"
    )


class QuotationItemUpdate(BaseModel):
    """人工审核修正（TRD 第十一章）：只更新提供的字段。"""

    supplier_name: str | None = Field(None, min_length=1)
    product_name: str | None = Field(None, min_length=1)
    model: str | None = None
    specification: str | None = None
    quantity: Decimal | None = Field(None, gt=0)
    unit: str | None = None
    unit_price: Decimal | None = Field(None, gt=0)
    currency: CurrencyCode | None = None
    tax_rate: Decimal | None = Field(None, ge=0, le=1)
    shipping_cost: Decimal | None = Field(None, ge=0)
    moq: Decimal | None = Field(None, ge=0)
    lead_time_days: int | None = Field(None, ge=0)
    payment_terms: str | None = None
    valid_until: date | None = None
    review_status: ReviewStatus | None = None

    @field_validator("supplier_name", "product_name")
    @classmethod
    def not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("不能为空白")
        return v.strip() if v is not None else None


class QuotationItemRead(BaseModel):
    """返回给前端的报价明细。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID | None = None
    source_file_id: UUID | None = None
    supplier_name: str | None = None
    product_name: str | None = None
    model: str | None = None
    specification: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    currency: str | None = None
    tax_rate: Decimal | None = None
    shipping_cost: Decimal | None = None
    moq: Decimal | None = None
    lead_time_days: int | None = None
    payment_terms: str | None = None
    valid_until: date | None = None
    source_reference: dict | None = None
    extraction_method: ExtractionMethod = ExtractionMethod.RULE
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW


class ItemList(BaseModel):
    total: int
    items: list[QuotationItemRead]
