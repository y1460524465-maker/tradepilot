"""报价记录标准结构（TRD 5.1）。

- 金额、数量、税率等计算字段一律使用 Decimal，禁止二进制浮点数直接参与财务计算。
- 未从文件中提取到的字段保持 None，由上层流程进入人工复核，不做猜测填充（TRD 7.3）。
"""

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CurrencyCode(str, Enum):
    """第一版常用币种；后续按贸易场景扩展。"""

    CNY = "CNY"
    USD = "USD"
    EUR = "EUR"
    JPY = "JPY"
    HKD = "HKD"


class ReviewStatus(str, Enum):
    """审核状态（TRD 3.2 / 8.2：不确定的数据必须标记，不得静默放行）。"""

    PENDING_REVIEW = "pending_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ExtractionMethod(str, Enum):
    """提取方式，用于来源追溯（TRD 5.1 / 7.3）。"""

    RULE = "rule"        # 规则/结构化读取（表头映射等）
    AI = "ai"            # 大模型辅助提取
    MANUAL = "manual"    # 人工录入/人工修正


class QuotationItemBase(BaseModel):
    """报价明细的统一结构。必需字段缺失会直接校验失败。"""

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
    """解析/提取流程提交报价明细时的负载。"""

    extraction_method: ExtractionMethod = ExtractionMethod.RULE
    source_file_id: str | None = Field(None, description="来源文件 ID")
    source_reference: dict | None = Field(
        None, description="来源追溯：工作表、页码、行号、原始文本片段等"
    )


class QuotationItemRead(QuotationItemBase):
    """返回给前端的报价明细。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    extraction_method: ExtractionMethod = ExtractionMethod.RULE
    source_file_id: str | None = None
    source_reference: dict | None = None
