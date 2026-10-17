"""阶段四测试：表头映射引擎、数值/币种/日期规范化、提取与修正接口。"""

from decimal import Decimal

import openpyxl
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tradepilot.app.core.config import settings
from tradepilot.app.db.base import Base
from tradepilot.app.db.session import get_db
from tradepilot.app.main import app
from tradepilot.app.services.field_mapping import map_headers, normalize_header
from tradepilot.app.services.normalization import parse_currency, parse_date, parse_decimal


# ---------- 表头映射引擎 ----------


def test_normalize_header_strips_punctuation():
    assert normalize_header(" 单价(元) ") == "单价元"
    assert normalize_header("Unit  Price") == "unitprice"
    assert normalize_header("交期(天)") == "交期天"


def test_map_exact_aliases():
    mapping, unmapped = map_headers(["供应商", "品名", "单价", "币种"])
    assert mapping["供应商"] == "supplier_name"
    assert mapping["品名"] == "product_name"
    assert mapping["单价"] == "unit_price"
    assert mapping["币种"] == "currency"
    assert unmapped == []


def test_map_english_headers():
    mapping, _ = map_headers(["Supplier", "Product Name", "Unit Price", "Currency", "Qty"])
    assert mapping["Supplier"] == "supplier_name"
    assert mapping["Product Name"] == "product_name"
    assert mapping["Unit Price"] == "unit_price"
    assert mapping["Currency"] == "currency"
    assert mapping["Qty"] == "quantity"


def test_longest_alias_wins():
    """报价数量 必须映射到 quantity 而不是 unit_price。"""
    mapping, _ = map_headers(["产品名称", "报价数量", "报价"])
    assert mapping["报价数量"] == "quantity"
    assert mapping["报价"] == "unit_price"


def test_parenthesized_header_substring_match():
    mapping, _ = map_headers(["单价(元)", "交期(天)"])
    assert mapping["单价(元)"] == "unit_price"
    assert mapping["交期(天)"] == "lead_time_days"


def test_unmapped_headers_reported():
    mapping, unmapped = map_headers(["产品名称", "单价", "备注", "神秘列"])
    assert mapping.get("备注") is None
    assert set(unmapped) == {"备注", "神秘列"}


def test_duplicate_field_first_column_wins():
    mapping, _ = map_headers(["单价", "价格"])
    assert mapping == {"单价": "unit_price"}


# ---------- 数值 / 币种 / 日期规范化 ----------


def test_parse_decimal_variants():
    assert parse_decimal("1,234.50") == Decimal("1234.50")
    assert parse_decimal("¥85.0") == Decimal("85.0")
    assert parse_decimal(" 0.35 元 ") == Decimal("0.35")
    assert parse_decimal(1000) == Decimal("1000")
    assert parse_decimal("abc") is None
    assert parse_decimal(None) is None


def test_parse_currency_variants():
    assert parse_currency("CNY") == "CNY"
    assert parse_currency("人民币") == "CNY"
    assert parse_currency("¥") == "CNY"
    assert parse_currency("usd") == "USD"
    assert parse_currency("比特币") is None
    assert parse_currency(None) is None


def test_parse_date_variants():
    assert parse_date("2026-12-31").isoformat() == "2026-12-31"
    assert parse_date("2026/1/5").isoformat() == "2026-01-05"
    assert parse_date("2026年12月31日").isoformat() == "2026-12-31"
    assert parse_date("not a date") is None


# ---------- 接口端到端（内存 SQLite） ----------


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_task(client) -> str:
    return client.post("/api/v1/tasks", json={"task_name": "提取测试"}).json()["id"]


def upload_xlsx(client, task_id: str, rows: list[list], filename="报价.xlsx") -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    resp = client.post(
        f"/api/v1/tasks/{task_id}/files",
        files=[("files", (filename, buf.getvalue(), "application/octet-stream"))],
    )
    assert resp.status_code == 201
    return resp.json()["items"][0]["id"]


def test_extract_unifies_different_headers(client):
    """不同表头（中文别名 + Unit Price）提取后字段统一。"""
    task_id = make_task(client)
    upload_xlsx(
        client,
        task_id,
        [
            ["供应商名称", "品名", "型号", "报价数量", "单位", "单价", "币种"],
            ["华信五金", "不锈钢螺栓", "M8x30", "1000", "件", "0.85", "人民币"],
        ],
        filename="报价A.xlsx",
    )
    upload_xlsx(
        client,
        task_id,
        [
            ["Supplier", "Product", "Unit Price", "Currency", "Qty"],
            ["宏达", "硅胶垫", "0.12", "CNY", "5000"],
        ],
        filename="报价B.xlsx",
    )

    summary = client.post(f"/api/v1/tasks/{task_id}/extract").json()
    assert summary["total_items"] == 2

    items = client.get(f"/api/v1/tasks/{task_id}/items").json()
    assert items["total"] == 2
    first = [i for i in items["items"] if i["supplier_name"] == "华信五金"][0]
    assert first["product_name"] == "不锈钢螺栓"
    assert Decimal(str(first["quantity"])) == Decimal("1000")
    assert Decimal(str(first["unit_price"])) == Decimal("0.85")
    assert first["currency"] == "CNY"
    assert first["review_status"] == "pending_review"
    second = [i for i in items["items"] if i["supplier_name"] == "宏达"][0]
    assert second["currency"] == "CNY"
    assert Decimal(str(second["unit_price"])) == Decimal("0.12")


def test_extract_is_idempotent(client):
    task_id = make_task(client)
    upload_xlsx(
        client,
        task_id,
        [["供应商", "产品名称", "单价", "币种"], ["A司", "螺栓", "1.00", "CNY"]],
    )
    client.post(f"/api/v1/tasks/{task_id}/extract")
    client.post(f"/api/v1/tasks/{task_id}/extract")  # 再来一次
    assert client.get(f"/api/v1/tasks/{task_id}/items").json()["total"] == 1


def test_extract_reports_unmapped_columns_and_missing_currency(client):
    task_id = make_task(client)
    upload_xlsx(
        client,
        task_id,
        [
            ["产品名称", "单价", "备注", "神秘列"],
            ["螺栓", "1.00", "含税", "???"],
        ],
    )
    summary = client.post(f"/api/v1/tasks/{task_id}/extract").json()
    result = summary["results"][0]
    assert result["item_count"] == 1
    assert any("未识别的表头" in w for w in result["warnings"])
    assert any("缺少币种" in w for w in result["warnings"])

    items = client.get(
        f"/api/v1/tasks/{task_id}/items", params={"review_status": "pending_review"}
    ).json()
    assert items["total"] == 1


def test_extract_skips_empty_rows(client):
    """空行在解析层即被过滤（dropna），有效行只提取 1 条。"""
    task_id = make_task(client)
    upload_xlsx(
        client,
        task_id,
        [
            ["供应商", "产品名称", "单价", "币种"],
            ["A司", "螺栓", "1.00", "CNY"],
            [None, None, None, None],
        ],
    )
    summary = client.post(f"/api/v1/tasks/{task_id}/extract").json()
    assert summary["total_items"] == 1
    assert summary["results"][0]["item_count"] == 1


def test_patch_item_updates_fields(client):
    task_id = make_task(client)
    upload_xlsx(
        client,
        task_id,
        [["产品名称", "单价"], ["螺栓", "1.00"]],
    )
    client.post(f"/api/v1/tasks/{task_id}/extract")
    item_id = client.get(f"/api/v1/tasks/{task_id}/items").json()["items"][0]["id"]

    resp = client.patch(
        f"/api/v1/items/{item_id}",
        json={"currency": "CNY", "review_status": "confirmed", "unit_price": "1.05"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["currency"] == "CNY"
    assert body["review_status"] == "confirmed"
    assert Decimal(str(body["unit_price"])) == Decimal("1.05")


def test_patch_unknown_item_404(client):
    import uuid as uuid_mod

    resp = client.patch(f"/api/v1/items/{uuid_mod.uuid4()}", json={"unit": "件"})
    assert resp.status_code == 404


def test_patch_blank_product_name_422(client):
    task_id = make_task(client)
    upload_xlsx(
        client, task_id, [["供应商", "产品名称", "单价", "币种"], ["A司", "螺栓", "1.00", "CNY"]]
    )
    client.post(f"/api/v1/tasks/{task_id}/extract")
    item_id = client.get(f"/api/v1/tasks/{task_id}/items").json()["items"][0]["id"]
    resp = client.patch(f"/api/v1/items/{item_id}", json={"product_name": "  "})
    assert resp.status_code == 422
