"""TradePilot 应用入口。

启动：uvicorn app.main:app --reload
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1 import ai, files, health, items, matching, review, tasks
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="AI 报价处理与供应商比价系统（MVP）",
)

# 统一接口前缀：/api/v1（TRD 第十三章）
app.include_router(health.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(items.router, prefix="/api/v1")
app.include_router(matching.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(review.router, prefix="/api/v1")

# 前端构建产物（阶段八）：存在则由后端直接托管，单服务即可使用完整系统
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
