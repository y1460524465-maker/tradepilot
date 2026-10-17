"""TradePilot 应用入口。

启动（在工作区根目录 E:\\TradePilot(workbdy) 下执行）：
    tradepilot\\.venv\\Scripts\\python -m uvicorn tradepilot.app.main:app --reload
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from tradepilot.app.api.v1 import ai, files, health, items, matching, review, tasks
from tradepilot.app.core.config import settings

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


class WebStaticFiles(StaticFiles):
    """修正 Windows 下 mimetypes 把 .js 判成 text/plain 的问题。

    浏览器对 ES Module 的 MIME 有严格校验，text/plain 会被直接拒绝执行，
    页面表现为白屏。这里按扩展名强制正确的 Content-Type。
    """

    FORCE_TYPES = {
        ".js": "application/javascript",
        ".mjs": "application/javascript",
        ".css": "text/css",
        ".svg": "image/svg+xml",
        ".json": "application/json",
    }

    def file_response(self, full_path, stat_result, scope, status_code=200):  # noqa: ANN001, ANN201
        response = super().file_response(full_path, stat_result, scope, status_code)
        if isinstance(response, Response):
            forced = self.FORCE_TYPES.get(Path(str(full_path)).suffix.lower())
            if forced:
                response.headers["content-type"] = forced
        return response


# 前端构建产物（阶段八）：存在则由后端直接托管，单服务即可使用完整系统
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", WebStaticFiles(directory=_frontend_dist, html=True), name="frontend")
