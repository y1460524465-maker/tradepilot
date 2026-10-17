"""人工审核与 Excel 导出（TRD 阶段七：完整业务闭环）。

审核：AI/规则提取结果默认 pending_review，人工确认后才视为采信数据。
导出：OpenPyXL 生成比价报告（比价结果 + 报价明细两张工作表），全部本地生成。
"""

import io
import uuid
from collections import Counter

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from tradepilot.app.models.comparison_task import ComparisonTask, TaskStatus
from tradepilot.app.models.quotation_item import QuotationItem, ReviewStatus
from tradepilot.app.models.product_match import ProductMatch
from tradepilot.app.services.comparison_service import Comparability, compute_task

_HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
_HEADER_FONT = Font(color="FFFFFF", bold=True)
_BEST_FILL = PatternFill("solid", fgColor="C6EFCE")   # 最低价标绿
_DIFF_FILL = PatternFill("solid", fgColor="FFC7CE")   # 涨幅超阈值标红
_DIFF_WARN_PCT = 10  # 涨幅超过 10% 标红提示


class ReviewService:
    def __init__(self, db: Session):
        self.db = db

    def _ensure_task(self, task_id: uuid.UUID) -> ComparisonTask:
        task = self.db.get(ComparisonTask, task_id)
        if task is None:
            raise KeyError(f"任务 {task_id} 不存在")
        return task

    def summary(self, task_id: uuid.UUID) -> dict:
        self._ensure_task(task_id)
        items = self.db.scalars(
            select(QuotationItem).where(QuotationItem.task_id == task_id)
        ).all()
        counts = Counter(it.review_status.value for it in items)
        issues = []
        for it in items:
            if it.unit_price is None:
                issues.append({"item_id": str(it.id), "issue": "缺少单价，无法参与比价"})
            if it.currency is None:
                issues.append({"item_id": str(it.id), "issue": "缺少币种，需人工确认"})
        return {
            "total_items": len(items),
            "by_status": dict(counts),
            "pending_review": counts.get(ReviewStatus.PENDING_REVIEW.value, 0),
            "issues": issues[:100],
        }

    def confirm(self, task_id: uuid.UUID, item_ids: list[uuid.UUID] | None, confirm_all: bool) -> int:
        """批量确认报价明细；confirm_all=True 时确认全部待审明细。返回确认条数。"""
        self._ensure_task(task_id)
        stmt = select(QuotationItem).where(
            QuotationItem.task_id == task_id,
            QuotationItem.review_status == ReviewStatus.PENDING_REVIEW,
        )
        if not confirm_all:
            if not item_ids:
                return 0
            stmt = stmt.where(QuotationItem.id.in_(item_ids))
        targets = self.db.scalars(stmt).all()
        for it in targets:
            it.review_status = ReviewStatus.CONFIRMED
        self.db.commit()
        return len(targets)


class ExportService:
    def __init__(self, db: Session):
        self.db = db

    def _ensure_task(self, task_id: uuid.UUID) -> ComparisonTask:
        task = self.db.get(ComparisonTask, task_id)
        if task is None:
            raise KeyError(f"任务 {task_id} 不存在")
        return task

    def export_xlsx(self, task_id: uuid.UUID) -> tuple[str, bytes]:
        """返回 (文件名, xlsx 字节流)。导出成功后任务状态置 completed。"""
        task = self._ensure_task(task_id)
        groups = compute_task(self.db, task_id)
        items = self.db.scalars(
            select(QuotationItem)
            .where(QuotationItem.task_id == task_id)
            .order_by(QuotationItem.created_at.asc())
        ).all()

        wb = Workbook()

        # ---- Sheet 1：比价结果
        ws = wb.active
        ws.title = "比价结果"
        headers = ["产品名称", "型号", "规格", "单位", "可比性", "报价数",
                   "最低价供应商", "最低单价", "最高涨幅%", "说明"]
        ws.append(headers)
        for g in groups:
            best = next((c for c in g.items if c.item_id == g.best_item_id), None)
            worst_pct = max(
                (c.diff_pct for c in g.items if c.diff_pct is not None), default=None
            )
            ws.append([
                g.product_name, g.model, g.specification, g.unit,
                {"comparable": "可比", "needs_review": "需人工确认",
                 "not_comparable": "不可比"}[g.comparability.value],
                g.item_count,
                best.supplier_name if best else None,
                float(best.unit_price) if best and best.unit_price is not None else None,
                float(worst_pct) if worst_pct is not None else None,
                "；".join(g.reasons),
            ])
        self._style(ws, highlight=[
            (row_idx, 7)  # 最低价供应商标绿
            for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2)
            if row[6].value is not None
        ] + [
            (row_idx, 9)  # 涨幅超阈值标红
            for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2)
            if row[8].value is not None and row[8].value > _DIFF_WARN_PCT
        ])

        # ---- Sheet 2：报价明细
        ws2 = wb.create_sheet("报价明细")
        headers2 = ["供应商", "产品名称", "型号", "规格", "数量", "单位", "单价", "币种",
                    "税率", "交期(天)", "付款条件", "有效期", "审核状态", "提取方式",
                    "来源文件", "来源位置"]
        ws2.append(headers2)
        for it in items:
            ref = it.source_reference or {}
            ws2.append([
                it.supplier_name, it.product_name, it.model, it.specification,
                float(it.quantity) if it.quantity is not None else None,
                it.unit,
                float(it.unit_price) if it.unit_price is not None else None,
                it.currency,
                float(it.tax_rate) if it.tax_rate is not None else None,
                it.lead_time_days, it.payment_terms,
                it.valid_until.isoformat() if it.valid_until else None,
                {"pending_review": "待复核", "confirmed": "已确认", "rejected": "已驳回"}[
                    it.review_status.value
                ],
                {"rule": "规则提取", "ai": "AI 提取", "manual": "人工"}[
                    it.extraction_method.value
                ],
                ref.get("file"),
                f"{ref.get('sheet', '')} 第{ref.get('row', '?')}行" if ref.get("row") else ref.get("source_text"),
            ])
        self._style(ws2)

        # 列宽
        for sheet in (ws, ws2):
            for col_idx in range(1, sheet.max_column + 1):
                sheet.column_dimensions[get_column_letter(col_idx)].width = 16

        buf = io.BytesIO()
        wb.save(buf)
        # 导出即完成（TRD：任务状态 completed）
        task.status = TaskStatus.COMPLETED
        self.db.commit()
        filename = f"比价报告_{task.task_name or task_id}.xlsx"
        return filename, buf.getvalue()

    @staticmethod
    def _style(ws, highlight: list[tuple[int, int]] | None = None) -> None:
        for cell in ws[1]:
            cell.fill = _HEADER_FILL
            cell.font = _HEADER_FONT
            cell.alignment = Alignment(horizontal="center")
        ws.freeze_panes = "A2"
        for row, col in highlight or []:
            ws.cell(row=row, column=col).fill = _DIFF_FILL
