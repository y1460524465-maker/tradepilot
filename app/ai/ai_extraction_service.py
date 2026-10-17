"""AI 辅助提取（TRD 9：只处理规则解析不了的内容，如不规则文本型 PDF）。

流程：文本块 → 大模型提取 → JSON Schema 校验 → 字段白名单映射 → 入库（AI 方法、待人工复核）。
铁律：
- AI 输出只作建议，所有记录 review_status=pending_review；
- 提取不到的字段保持 None，绝不猜测填充；
- 每条记录带来源追溯（模型名、原始文本片段）；
- ai_enabled 默认关闭。
"""

import uuid
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tradepilot.app.ai import provider as ai_provider_module
from tradepilot.app.core.config import settings
from tradepilot.app.models.quotation_item import ExtractionMethod, QuotationItem, ReviewStatus
from tradepilot.app.models.uploaded_file import FileStatus, UploadedFile
from tradepilot.app.parsers import registry
from tradepilot.app.services import normalization
from tradepilot.app.services.file_service import FileService

SYSTEM_PROMPT = """你是报价单字段提取助手。从给定的报价文本中提取每一行报价信息。
只输出 JSON，格式：
{"items": [{"supplier_name": str|null, "product_name": str|null, "model": str|null,
  "specification": str|null, "quantity": number|null, "unit": str|null,
  "unit_price": number|null, "currency": "CNY"|"USD"|..., "tax_rate": number|null,
  "lead_time_days": int|null, "payment_terms": str|null, "valid_until": "YYYY-MM-DD"|null,
  "source_text": str}]}
规则：
1. 只提取文本中明确出现的信息，看不出来就填 null，禁止猜测或编造；
2. 每条 item 必须带 source_text（该行原始文本片段）以便追溯；
3. 数值去掉货币符号和千分位再输出。"""


class AIItem(BaseModel):
    """模型输出的 Schema 校验模型（TRD 9.2：模型输出必须过 JSON Schema 校验）。"""

    supplier_name: str | None = None
    product_name: str | None = None
    model: str | None = None
    specification: str | None = None
    quantity: float | None = Field(None, gt=0)
    unit: str | None = None
    unit_price: float | None = Field(None, gt=0)
    currency: str | None = None
    tax_rate: float | None = Field(None, ge=0)
    lead_time_days: int | None = Field(None, ge=0)
    payment_terms: str | None = None
    valid_until: str | None = None
    source_text: str | None = None


class AIExtractSummary:
    def __init__(self, task_id: uuid.UUID):
        self.task_id = task_id
        self.files: list[dict] = []  # [{filename, item_count, skipped, errors}]
        self.warnings: list[str] = []

    @property
    def total_items(self) -> int:
        return sum(f["item_count"] for f in self.files)


def _file_needs_ai(db: Session, file: UploadedFile) -> bool:
    """规则提取没有产出的文件才交给 AI（TRD：AI 只兜底，不重复劳动）。

    只看 RULE 方法的产出：AI 自己的产出不算（否则重跑 AI 会被自己上次的结果挡住）。
    """
    has_rule_items = db.scalar(
        select(QuotationItem.id)
        .where(
            QuotationItem.source_file_id == file.id,
            QuotationItem.extraction_method == ExtractionMethod.RULE,
        )
        .limit(1)
    )
    return has_rule_items is None


def build_text_from_file(raw) -> str:
    """把解析结果压成给模型的纯文本（文本型 PDF 的行/表格文本）。"""
    lines: list[str] = []
    for sheet in raw.sheets:
        if sheet.columns:
            lines.append(" | ".join(sheet.columns))
        for row in sheet.rows:
            lines.append(" | ".join("" if v is None else str(v) for v in row))
    return "\n".join(lines)[: settings.ai_max_text_chars]


class AIExtractionService:
    def __init__(self, db: Session, provider: ai_provider_module.AIProvider | None = None):
        self.db = db
        self.provider = provider
        self._files = FileService(db)

    def extract_task(self, task_id: uuid.UUID) -> AIExtractSummary:
        if not settings.ai_enabled and self.provider is None:
            raise PermissionError(
                "AI 辅助提取未启用：真实企业数据未经授权不得发送第三方模型 API，"
                "如需启用请在 .env 设置 AI_ENABLED=true 并配置 AI_API_KEY"
            )
        self._files._ensure_task(task_id)  # 404 保护
        self._files.parse_task_files(task_id)  # 未解析的先解析
        files = (
            self.db.scalars(
                select(UploadedFile).where(
                    UploadedFile.task_id == task_id,
                    UploadedFile.status == FileStatus.PARSED,
                )
            )
            .all()
        )
        summary = AIExtractSummary(task_id=task_id)
        for file in files:
            if not _file_needs_ai(self.db, file):
                continue
            self._extract_file(file, summary)
        self.db.commit()
        return summary

    def _extract_file(self, file: UploadedFile, summary: AIExtractSummary) -> None:
        entry = {"file_id": file.id, "filename": file.original_filename, "item_count": 0, "errors": []}
        summary.files.append(entry)
        try:
            raw = registry.parse_file(file.file_type, Path(file.storage_path))
        except Exception as e:  # noqa: BLE001
            entry["errors"].append(f"文件读取失败：{e}")
            return
        text = build_text_from_file(raw)
        if not text.strip():
            entry["errors"].append("无可提取文本")
            return

        provider = self.provider or ai_provider_module.get_provider()
        try:
            payload = provider.extract_json(SYSTEM_PROMPT, text)
        except Exception as e:  # noqa: BLE001
            entry["errors"].append(f"模型调用/解析失败：{e}")
            return

        # 幂等：清掉本文件之前的 AI 提取结果（不影响规则提取结果）
        self.db.execute(
            delete(QuotationItem).where(
                QuotationItem.source_file_id == file.id,
                QuotationItem.extraction_method == ExtractionMethod.AI,
            )
        )

        for raw_item in payload.get("items", []):
            try:
                item = AIItem(**raw_item)
            except ValidationError as e:
                summary.warnings.append(
                    f"文件「{file.original_filename}」一条 AI 结果未通过 Schema 校验，已丢弃：{e.errors()[0].get('msg')}"
                )
                continue
            if not item.product_name and item.unit_price is None:
                continue  # 无提取价值的行
            currency = normalization.parse_currency(item.currency)
            if item.currency and currency is None:
                summary.warnings.append(f"AI 返回无法识别的币种：{item.currency}（已置空待复核）")
            self.db.add(
                QuotationItem(
                    task_id=file.task_id,
                    source_file_id=file.id,
                    supplier_name=normalization.clean_str(item.supplier_name),
                    product_name=normalization.clean_str(item.product_name),
                    model=normalization.clean_str(item.model),
                    specification=normalization.clean_str(item.specification),
                    quantity=normalization.parse_decimal(item.quantity),
                    unit=normalization.clean_str(item.unit),
                    unit_price=normalization.parse_decimal(item.unit_price),
                    currency=currency,
                    tax_rate=normalization.parse_decimal(item.tax_rate),
                    lead_time_days=item.lead_time_days,
                    payment_terms=normalization.clean_str(item.payment_terms),
                    valid_until=normalization.parse_date(item.valid_until),
                    source_reference={
                        "file": file.original_filename,
                        "ai_model": settings.ai_model,
                        "source_text": (item.source_text or "")[:500],
                    },
                    extraction_method=ExtractionMethod.AI,
                    review_status=ReviewStatus.PENDING_REVIEW,
                )
            )
            entry["item_count"] += 1
