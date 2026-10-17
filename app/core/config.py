"""应用配置。

所有配置项均支持通过环境变量或 .env 文件覆盖。
数据库密码、模型 API Key 等敏感信息不得写入源代码（TRD 15.2）。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "TradePilot"
    version: str = "0.1.0"
    environment: str = "development"  # development / testing / production

    # 阶段二启用：PostgreSQL 连接串
    database_url: str = "postgresql+psycopg://tradepilot:tradepilot@localhost:5432/tradepilot"

    # 文件存储（TRD 第六章）
    storage_dir: str = "storage"
    max_upload_size_mb: int = 20      # 单文件上限（TRD 6.3 示例值）
    max_files_per_task: int = 20      # 单任务文件数上限


settings = Settings()
