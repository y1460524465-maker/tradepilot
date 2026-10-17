"""TradePilot 应用入口。

启动：uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.api.v1 import health, tasks
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="AI 报价处理与供应商比价系统（MVP）",
)

# 统一接口前缀：/api/v1（TRD 第十三章）
app.include_router(health.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
