"""SQLAlchemy 声明式基类（只定义 Base，避免循环导入；模型汇聚见 app/models/__init__.py）。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
