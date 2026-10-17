"""共享测试环境：内存 SQLite + 临时存储目录。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import tradepilot.app.core.config as config_module

from tradepilot.app.db.base import Base
from tradepilot.app.db.session import get_db
from tradepilot.app.main import app


@pytest.fixture()
def session_factory(tmp_path, monkeypatch):
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

    # 原地修改单例属性（不要替换对象引用：各服务模块 import 的是旧引用）
    cfg = config_module.settings
    monkeypatch.setattr(cfg, "storage_dir", str(tmp_path), raising=False)
    monkeypatch.setattr(cfg, "max_upload_size_mb", 1, raising=False)
    app.dependency_overrides[get_db] = override_get_db
    yield TestingSession
    app.dependency_overrides.clear()


@pytest.fixture()
def client(session_factory):
    with TestClient(app) as c:
        yield c
