"""Alembic 迁移环境。

连接串统一从应用配置（app.core.config.settings）读取，
支持被环境变量 TRADEPILOT_DATABASE_URL 覆盖，避免在 alembic.ini 中硬编码密码。
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# 保证 alembic 命令在任何 cwd 调用时都能导入 tradepilot 包（需工作区根目录在 sys.path）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tradepilot.app.core.config import settings  # noqa: E402
from tradepilot.app.db.base import Base  # noqa: E402
import tradepilot.app.models  # noqa: E402,F401  确保所有模型注册到 Base.metadata

config = context.config

# 数据库连接串以应用配置为准（TRD 15.2：密码不写入源代码）
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：仅生成 SQL 脚本，不连接数据库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
