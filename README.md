# TradePilot

AI 报价处理与供应商比价系统（MVP）。技术栈与业务规则依据《TradePilot 技术需求文档 TRD V1.0》。

## 技术栈

- 后端：Python 3.13 + FastAPI + SQLAlchemy + Alembic + Pydantic
- 数据库：PostgreSQL 16（Docker Compose）
- 解析：Pandas / OpenPyXL / PyMuPDF（Excel / CSV / PDF）
- AI 辅助：DeepSeek（OpenAI 兼容接口，默认关闭，需显式授权启用）
- 前端：Vue 3 + Vite

## 业务流程

创建比价任务 → 上传报价文件（xlsx/csv/pdf）→ 解析提取（表头映射 + 格式规范化，AI 兜底）→
产品匹配（精确/规则/模糊三级，规格冲突禁止自动合并）→ 比价计算（确定性 Python + Decimal）→
人工审核 → 导出比价报告 xlsx

## 本地开发

```bash
# 1. 数据库
docker compose up -d

# 2. 后端（首次先建虚拟环境装依赖）
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m alembic upgrade head     # 数据库迁移
.venv\Scripts\python -m uvicorn app.main:app --reload

# 3. 前端（可选：构建后由后端直接托管，无需单独起服务）
cd frontend
npm install
npm run build

# 4. 测试
.venv\Scripts\python -m pytest
```

- 系统入口（含前端）：<http://127.0.0.1:8000/>
- Swagger 文档：<http://127.0.0.1:8000/docs>
- 前端开发模式：`cd frontend && npm run dev`（Vite 代理 /api 到 8000 端口）
- AI 功能：复制 `.env.example` 为 `.env`，设置 `TRADEPILOT_AI_ENABLED=true` 与
  `TRADEPILOT_AI_API_KEY`。默认关闭——真实企业数据未经授权不得发送第三方模型 API。

## 开发约定（TRD 第二十章）

- 每个阶段必须有明确交付物，先做可运行的最小版本再重构。
- 关键价格计算由确定性 Python 代码完成，模型输出必须经过程序校验。
- 不确定的数据进入人工复核，不静默产生结果。
