"""任务接口测试：使用内存 SQLite，覆盖创建/列表/详情/404（TRD 第十七章）。"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def client():
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

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_create_task_returns_201(client):
    resp = client.post("/api/v1/tasks", json={"task_name": "10月螺栓比价", "created_by": "张三"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["task_name"] == "10月螺栓比价"
    assert body["status"] == "created"
    assert body["created_by"] == "张三"
    uuid.UUID(body["id"])  # id 必须是合法 UUID


def test_task_persists_in_session(client):
    created = client.post("/api/v1/tasks", json={"task_name": "任务B"}).json()
    fetched = client.get(f"/api/v1/tasks/{created['id']}").json()
    assert fetched["task_name"] == "任务B"
    assert fetched["created_at"] == created["created_at"]


def test_list_tasks_returns_total_and_items(client):
    client.post("/api/v1/tasks", json={"task_name": "任务1"})
    client.post("/api/v1/tasks", json={"task_name": "任务2"})
    resp = client.get("/api/v1/tasks")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


def test_get_unknown_task_returns_404(client):
    resp = client.get(f"/api/v1/tasks/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_create_task_with_blank_name_fails_422(client):
    resp = client.post("/api/v1/tasks", json={"task_name": "  "})
    assert resp.status_code == 422


def test_create_task_name_over_200_chars_fails_422(client):
    resp = client.post("/api/v1/tasks", json={"task_name": "x" * 201})
    assert resp.status_code == 422
