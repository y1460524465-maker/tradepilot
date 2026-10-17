"""健康检查接口测试。"""

from fastapi.testclient import TestClient

from tradepilot.app.main import app

client = TestClient(app)


def test_health_returns_ok():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "TradePilot"
    assert "version" in body
