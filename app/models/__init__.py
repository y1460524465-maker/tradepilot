"""模型汇聚点：导入此包即可让所有模型注册到 Base.metadata（供 Alembic autogenerate 发现）。"""

from app.models.comparison_task import ComparisonTask, TaskStatus  # noqa: F401
from app.models.uploaded_file import FileStatus, FileTypeEnum, UploadedFile  # noqa: F401
