"""模型汇聚点：导入此包即可让所有模型注册到 Base.metadata（供 Alembic autogenerate 发现）。"""

from tradepilot.app.models.comparison_task import ComparisonTask, TaskStatus  # noqa: F401
from tradepilot.app.models.product_match import MatchStatus, MatchType, ProductMatch  # noqa: F401
from tradepilot.app.models.quotation_item import ExtractionMethod, QuotationItem, ReviewStatus  # noqa: F401
from tradepilot.app.models.uploaded_file import FileStatus, FileTypeEnum, UploadedFile  # noqa: F401
