# TradePilot

AI 报价处理与供应商比价系统（MVP）。技术栈与业务规则依据《TradePilot 技术需求文档 TRD V1.0》。

## 技术栈

- Python 3.13 + FastAPI + Pydantic
- PostgreSQL 16（Docker Compose，阶段二启用）
- Pandas / OpenPyXL / PyMuPDF（阶段三启用）
- DeepSeek API（阶段六启用）

## 本地开发

```bash
# 1. 创建虚拟环境并安装依赖（首次）
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# 2. 启动服务
.venv\Scripts\python -m uvicorn app.main:app --reload

# 3. 验证健康检查
curl http://127.0.0.1:8000/api/v1/health

# 4. 运行测试
.venv\Scripts\python -m pytest
```

- Swagger 文档：<http://127.0.0.1:8000/docs>
- 数据库：`docker compose up -d`（阶段二启用）

## 开发约定（TRD 第二十章）

- 每个阶段必须有明确交付物，先做可运行的最小版本再重构。
- 关键价格计算由确定性 Python 代码完成，模型输出必须经过程序校验。
- 不确定的数据进入人工复核，不静默产生结果。
