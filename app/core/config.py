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

    # 阶段六：大模型辅助提取（TRD 第九章；AI 只辅助不决策）
    ai_enabled: bool = False          # 总开关：默认关闭，真实企业数据未经授权不出第三方 API
    ai_base_url: str = "https://api.deepseek.com/v1"
    ai_api_key: str = ""              # 走 .env，不进代码
    ai_model: str = "deepseek-chat"
    ai_timeout_seconds: int = 60
    ai_max_text_chars: int = 12000    # 送入模型的文本上限（截断保护）


settings = Settings()
