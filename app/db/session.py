"""数据库连接与会话管理。

- 同步引擎 + SessionLocal，MVP 阶段保持简单；引入后台任务时再评估异步驱动。
- get_db 作为 FastAPI 依赖注入，请求结束自动关闭会话。
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tradepilot.app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
