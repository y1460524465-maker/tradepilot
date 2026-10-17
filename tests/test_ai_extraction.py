"""阶段六测试：AI 辅助提取（MockProvider，不访问网络）。

覆盖：默认关闭（403）、Mock 提取入库、Schema 校验丢弃脏数据、AI 结果幂等、
不覆盖规则提取结果、来源追溯。
"""

import io
import uuid

import openpyxl
import pytest

from tradepilot.app.ai.provider import MockProvider
from tradepilot.app.models.quotation_item import ExtractionMethod, QuotationItem
from tradepilot.app.schemas.quotation import QuotationItemCreate


def make_task(client) -> str:
    return client.post("/api/v1/tasks", json={"task_name": "AI提取测试"}).json()["id"]


def upload_empty_product_xlsx(client, task_id):
    """上传一份"AI 才能读"的文件：有行数据但表头无法映射（模拟不规则文本）。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["产品及规格说明", "价格资料"])  # 表头映射不上任何字段
    ws.append(["不锈钢螺栓 M8x30 GB/T5783 1000件 0.85元"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = client.post(
        f"/api/v1/tasks/{task_id}/files",
        files={"files": ("怪表头.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code in (200, 201)
    return resp.json()["items"][0]["id"]


def ai_handler(text: str) -> dict:
    if "不锈钢螺栓" not in text:
        return {"items": []}
    return {
        "items": [
            {
                "product_name": "不锈钢螺栓",
                "model": "M8x30",
                "quantity": 1000,
                "unit": "件",
                "unit_price": "0.85",
                "currency": "CNY",
                "source_text": "不锈钢螺栓 M8x30 GB/T5783 1000件 0.85元",
            },
            {  # 脏数据：负单价 → Schema 校验失败，应被丢弃
                "product_name": "坏数据", "unit_price": -5, "source_text": "x",
            },
            {  # 无产品名且无单价 → 跳过
                "supplier_name": "无名氏", "source_text": "y",
            },
        ]
    }


def test_ai_extract_disabled_by_default(client, monkeypatch):
    task_id = make_task(client)
    resp = client.post(f"/api/v1/tasks/{task_id}/ai_extract")
    assert resp.status_code == 403
    assert "AI_ENABLED" in resp.json()["detail"]


def test_ai_extract_with_mock_provider(client, session_factory, monkeypatch):
    import tradepilot.app.core.config as config_module
    monkeypatch.setattr(config_module.settings, "ai_enabled", True)

    task_id = make_task(client)
    upload_empty_product_xlsx(client, task_id)

    import tradepilot.app.ai.ai_extraction_service as mod
    original = mod.ai_provider_module.get_provider
    monkeypatch.setattr(mod.ai_provider_module, "get_provider", lambda: MockProvider(ai_handler))

    summary = client.post(f"/api/v1/tasks/{task_id}/ai_extract").json()
    assert summary["total_items"] == 1  # 脏数据和无价值行被过滤

    items = client.get(f"/api/v1/tasks/{task_id}/items").json()["items"]
    item = items[0]
    assert item["extraction_method"] == "ai"
    assert item["review_status"] == "pending_review"  # AI 结果必须人工复核
    assert Decimal_check(item["unit_price"]) == 0.85
    assert item["source_reference"]["source_text"].startswith("不锈钢螺栓")


def Decimal_check(v):
    return float(v)


def test_ai_extract_idempotent_and_keeps_rule_results(client, session_factory, monkeypatch):
    import tradepilot.app.core.config as config_module
    monkeypatch.setattr(config_module.settings, "ai_enabled", True)

    task_id = make_task(client)
    file_id = upload_empty_product_xlsx(client, task_id)

    # 先手工造一条"规则提取"记录（挂空来源，模拟规则阶段产物），验证 AI 重跑不清掉它
    db = session_factory()
    try:
        db.add(
            QuotationItem(
                task_id=uuid.UUID(task_id),
                product_name="规则产物",
                extraction_method=ExtractionMethod.RULE,
            )
        )
        db.commit()
    finally:
        db.close()

    import tradepilot.app.ai.ai_extraction_service as mod
    monkeypatch.setattr(mod.ai_provider_module, "get_provider", lambda: MockProvider(ai_handler))

    first = client.post(f"/api/v1/tasks/{task_id}/ai_extract").json()
    second = client.post(f"/api/v1/tasks/{task_id}/ai_extract").json()
    assert first["total_items"] == second["total_items"] == 1

    items = client.get(f"/api/v1/tasks/{task_id}/items").json()["items"]
    assert len(items) == 2  # 1 条规则 + 1 条 AI（AI 重跑不累积）
    assert sum(1 for i in items if i["extraction_method"] == "rule") == 1


def test_ai_extract_unknown_task_404(client):
    resp = client.post(f"/api/v1/tasks/{uuid.uuid4()}/ai_extract")
    assert resp.status_code == 404
