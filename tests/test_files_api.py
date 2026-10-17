"""文件上传与解析接口测试（TRD 第十七章：上传/解析/校验/失败处理）。

用内存构造真实的 xlsx / csv / pdf 字节流，覆盖：
格式校验（扩展名+magic bytes）、大小限制、解析结果、失败标记、下载权限。
"""

import io
import uuid

import fitz  # PyMuPDF
import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tradepilot.app.core.config import settings
from tradepilot.app.db.base import Base
from tradepilot.app.db.session import get_db
from tradepilot.app.main import app


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

    # 直接修改 settings 实例属性（monkeypatch 自动还原），各模块引用同一对象
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_task(client) -> str:
    return client.post("/api/v1/tasks", json={"task_name": "文件测试任务"}).json()["id"]


def make_xlsx(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "报价"
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    buf = io.BytesIO(doc.tobytes())
    doc.close()
    return buf.getvalue()


XLSX_ROWS = [
    ["供应商", "产品名称", "型号", "数量", "单位", "单价", "币种"],
    ["供应商A", "不锈钢螺栓", "M8x30", 1000, "件", 0.85, "CNY"],
    ["供应商A", "不锈钢螺母", "M8", 2000, "件", 0.35, "CNY"],
]


def test_upload_xlsx_and_parse(client):
    task_id = make_task(client)
    files = [("files", ("报价A.xlsx", make_xlsx(XLSX_ROWS), "application/octet-stream"))]
    resp = client.post(f"/api/v1/tasks/{task_id}/files", files=files)
    assert resp.status_code == 201
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["original_filename"] == "报价A.xlsx"
    assert body["items"][0]["file_type"] == "xlsx"
    assert body["items"][0]["status"] == "uploaded"

    parsed = client.post(f"/api/v1/tasks/{task_id}/parse").json()
    assert parsed["results"][0]["status"] == "parsed"
    assert parsed["results"][0]["row_count"] == 2

    detail = client.get(f"/api/v1/tasks/{task_id}/files/{body['items'][0]['id']}").json()
    preview = detail["parsed_preview"]
    assert preview["sheets"][0]["columns"] == ["供应商", "产品名称", "型号", "数量", "单位", "单价", "币种"]
    assert preview["sheets"][0]["preview_rows"][0][0] == "供应商A"


def test_upload_csv_gbk_and_parse(client):
    task_id = make_task(client)
    content = "供应商,产品名称,单价,币种\n供应商B,硅胶垫,0.12,CNY\n供应商B,密封圈,0.45,CNY\n".encode("gbk")
    files = [("files", ("报价B.csv", content, "text/csv"))]
    resp = client.post(f"/api/v1/tasks/{task_id}/files", files=files)
    assert resp.status_code == 201

    parsed = client.post(f"/api/v1/tasks/{task_id}/parse").json()
    assert parsed["results"][0]["status"] == "parsed"
    assert parsed["results"][0]["row_count"] == 2


def test_upload_pdf_and_parse(client):
    task_id = make_task(client)
    pdf = make_pdf("供应商C 产品名称 型号 单价\n供应商C 六角螺栓 M10 1.20")
    files = [("files", ("报价C.pdf", pdf, "application/pdf"))]
    resp = client.post(f"/api/v1/tasks/{task_id}/files", files=files)
    assert resp.status_code == 201

    parsed = client.post(f"/api/v1/tasks/{task_id}/parse").json()
    assert parsed["results"][0]["status"] == "parsed"


def test_reject_fake_extension(client):
    """扩展名是 .xlsx 但内容是文本 → 拒绝（magic bytes 校验）。"""
    task_id = make_task(client)
    files = [("files", ("fake.xlsx", b"this is not excel", "application/octet-stream"))]
    resp = client.post(f"/api/v1/tasks/{task_id}/files", files=files)
    assert resp.status_code == 400


def test_reject_unsupported_extension(client):
    task_id = make_task(client)
    files = [("files", ("doc.docx", b"PK\x03\x04whatever", "application/octet-stream"))]
    resp = client.post(f"/api/v1/tasks/{task_id}/files", files=files)
    assert resp.status_code == 400
    assert "不支持" in resp.json()["detail"]


def test_reject_oversized_file(client):
    task_id = make_task(client)
    big = b"PK\x03\x04" + b"0" * (1024 * 1024 + 1)  # 超过 1MB 测试上限
    files = [("files", ("big.xlsx", big, "application/octet-stream"))]
    resp = client.post(f"/api/v1/tasks/{task_id}/files", files=files)
    assert resp.status_code == 413


def test_upload_to_unknown_task_404(client):
    files = [("files", ("a.csv", b"col1,col2\n1,2", "text/csv"))]
    resp = client.post(f"/api/v1/tasks/{uuid.uuid4()}/files", files=files)
    assert resp.status_code == 404


def test_file_belongs_to_task(client):
    """文件归属于任务 A 时，从任务 B 访问必须 404（下载权限校验）。"""
    task_a = make_task(client)
    task_b = make_task(client)
    files = [("files", ("a.csv", "c1,c2\n1,2".encode(), "text/csv"))]
    file_id = client.post(f"/api/v1/tasks/{task_a}/files", files=files).json()["items"][0]["id"]

    assert client.get(f"/api/v1/tasks/{task_b}/files/{file_id}").status_code == 404
    assert client.get(f"/api/v1/tasks/{task_a}/files/{file_id}/download").status_code == 200


def test_parse_failure_marks_file_failed(client):
    """内容能过 magic 校验但 pandas 读不了 → 文件标记 parse_failed 并记录原因。"""
    task_id = make_task(client)
    # ZIP 头合法但不是真正的 Excel
    broken = b"PK\x03\x04" + b"\x00" * 64
    files = [("files", ("broken.xlsx", broken, "application/octet-stream"))]
    file_id = client.post(f"/api/v1/tasks/{task_id}/files", files=files).json()["items"][0]["id"]

    parsed = client.post(f"/api/v1/tasks/{task_id}/parse").json()
    result = parsed["results"][0]
    assert result["status"] == "parse_failed"
    assert result["error"]

    detail = client.get(f"/api/v1/tasks/{task_id}/files/{file_id}").json()
    assert detail["status"] == "parse_failed"
    assert detail["error_message"]
