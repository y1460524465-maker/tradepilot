"""共享测试环境：内存 SQLite + 临时存储目录。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.config as config_module
from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app


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

    test_settings = Settings(storage_dir=str(tmp_path))
    monkeypatch.setattr(config_module, "settings", test_settings)
    app.dependency_overrides[get_db] = override_get_db
    yield TestingSession
    app.dependency_overrides.clear()


@pytest.fixture()
def client(session_factory):
    with TestClient(app) as c:
        yield c
