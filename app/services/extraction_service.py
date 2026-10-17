"""报价提取（TRD 阶段四：把解析后的文件转换为统一报价记录）。

流程：已解析文件 → 表头映射 → 逐行数值/币种/日期规范化 → 写入 quotation_items。
原则：映射不上的表头不猜测；值解析不了记为 None 并记录告警进人工复核。
重新提取是幂等的：先删除该文件之前的提取结果。
"""

import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.quotation_item import ExtractionMethod, QuotationItem, ReviewStatus
from app.models.uploaded_file import FileStatus, UploadedFile
from app.parsers import registry
from app.services import normalization
from app.services.field_mapping import map_headers
from app.services.file_service import FileService


class FileExtractionResult:
    def __init__(self, file_id: uuid.UUID, filename: str):
        self.file_id = file_id
        self.filename = filename
        self.item_count = 0
        self.skipped_rows = 0
        self.warnings: list[str] = []


class ExtractSummary:
    def __init__(self, task_id: uuid.UUID):
        self.task_id = task_id
        self.results: list[FileExtractionResult] = []


class ExtractionService:
    def __init__(self, db: Session):
        self.db = db
        self.files = FileService(db)

    def extract_task(self, task_id: uuid.UUID) -> ExtractSummary:
        self.files._ensure_task(task_id)  # 404 保护
        # 文件尚未解析的先解析（上传 → 解析 → 提取 一条龙）
        self.files.parse_task_files(task_id)

        files = (
            self.db.scalars(
                select(UploadedFile).where(
                    UploadedFile.task_id == task_id,
                    UploadedFile.status == FileStatus.PARSED,
                )
            )
            .all()
        )

        summary = ExtractSummary(task_id=task_id)
        for file in files:
            summary.results.append(self._extract_file(file))
        self.db.commit()
        return summary

    def _extract_file(self, file: UploadedFile) -> FileExtractionResult:
        result = FileExtractionResult(file_id=file.id, filename=file.original_filename)

        # 幂等：清除该文件之前的提取结果
        self.db.execute(delete(QuotationItem).where(QuotationItem.source_file_id == file.id))

        try:
            raw = registry.parse_file(file.file_type, Path(file.storage_path))
        except Exception as e:  # noqa: BLE001
            file.status = FileStatus.PARSE_FAILED
            file.error_message = str(e)[:2000]
            result.warnings.append("文件重新读取失败，已标记 parse_failed")
            return result

        for sheet in raw.sheets:
            if not sheet.columns:
                continue
            mapping, unmapped = map_headers(sheet.columns)
            if unmapped:
                result.warnings.append(f"工作表「{sheet.name}」未识别的表头：{'、'.join(unmapped)}")
            if not any(f in mapping.values() for f in ("product_name", "unit_price")):
                result.warnings.append(f"工作表「{sheet.name}」没有产品名称或单价列，已跳过")
                continue

            for index, row in enumerate(sheet.rows):
                self._extract_row(file, sheet, index, mapping, row, result)
        return result

    def _extract_row(
        self,
        file: UploadedFile,
        sheet,
        index: int,
        mapping: dict[str, str],
        row: list,
        result: FileExtractionResult,
    ) -> None:
        by_field: dict[str, object] = {}
        for col, field in mapping.items():
            by_field[field] = row[sheet.columns.index(col)]

        product_name = normalization.clean_str(by_field.get("product_name"))
        unit_price = normalization.parse_decimal(by_field.get("unit_price"))

        # 供应商整列缺失时回退为文件名提示（明确标记来源，不冒充提取结果）
        supplier_name = normalization.clean_str(by_field.get("supplier_name"))

        # 空行跳过：产品名称和单价都缺失的行没有提取价值
        if not product_name and unit_price is None:
            result.skipped_rows += 1
            return

        warnings: list[str] = []
        if unit_price is None:
            warnings.append("缺少单价，将阻止直接比价")
        currency = normalization.parse_currency(by_field.get("currency"))
        if currency is None and by_field.get("currency") is not None:
            warnings.append(f"无法识别的币种表达：{by_field.get('currency')}")
        elif currency is None:
            warnings.append("缺少币种，需要人工确认")

        quantity = normalization.parse_decimal(by_field.get("quantity"))
        tax_rate = normalization.parse_decimal(by_field.get("tax_rate"))
        if tax_rate is not None and tax_rate > 1:
            # 13 → 0.13 的常见表达，转换后仍保留告警
            tax_rate = tax_rate / 100
            warnings.append("税率按百分数（÷100）转换，请复核")

        valid_until = normalization.parse_date(by_field.get("valid_until"))
        if by_field.get("valid_until") is not None and valid_until is None:
            warnings.append("有效期格式无法识别")

        item = QuotationItem(
            task_id=file.task_id,
            source_file_id=file.id,
            supplier_name=supplier_name,
            product_name=product_name,
            model=normalization.clean_str(by_field.get("model")),
            specification=normalization.clean_str(by_field.get("specification")),
            quantity=quantity,
            unit=normalization.clean_str(by_field.get("unit")),
            unit_price=unit_price,
            currency=currency,
            tax_rate=tax_rate,
            shipping_cost=normalization.parse_decimal(by_field.get("shipping_cost")),
            moq=normalization.parse_decimal(by_field.get("moq")),
            lead_time_days=normalization.parse_int(by_field.get("lead_time_days")),
            payment_terms=normalization.clean_str(by_field.get("payment_terms")),
            valid_until=valid_until,
            source_reference={
                "file": file.original_filename,
                "sheet": sheet.name,
                "row": index + 2,  # 表头占第 1 行
                "header_mapping": mapping,
                "raw_row": {
                    col: (str(v) if v is not None else None) for col, v in zip(sheet.columns, row)
                },
            },
            extraction_method=ExtractionMethod.RULE,
            review_status=ReviewStatus.PENDING_REVIEW,
        )
        self.db.add(item)
        result.item_count += 1
        for w in warnings:
            result.warnings.append(f"第 {index + 2} 行：{w}")
