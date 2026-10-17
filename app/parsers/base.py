"""解析器基础定义（TRD 6.4：统一的 BaseQuotationParser 接口）。

解析器输出统一的原始报价数据结构；业务服务不需要了解每种文件的具体解析细节。
"""

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field


class RawSheet(BaseModel):
    """一张工作表 / 一个数据块的原始内容。"""

    name: str = Field(..., description="工作表名 / 页码 / 数据块名")
    columns: list[str] = Field(default_factory=list, description="表头（空表可为空列表）")
    row_count: int = Field(0, ge=0, description="数据行总数（不含表头）")
    rows: list[list] = Field(default_factory=list, description="全部数据行（不含表头）")


class RawFileContent(BaseModel):
    """一个文件的统一解析结果。"""

    file_type: str
    sheets: list[RawSheet] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list, description="解析过程中的提示信息")

    @property
    def total_rows(self) -> int:
        return sum(s.row_count for s in self.sheets)

    def to_preview(self, max_rows: int = 50) -> dict:
        """生成入库的 parsed_preview 字典（限制预览行数）。"""
        return {
            "file_type": self.file_type,
            "total_rows": self.total_rows,
            "sheets": [
                {
                    "name": s.name,
                    "columns": s.columns,
                    "row_count": s.row_count,
                    "preview_rows": s.rows[:max_rows],
                }
                for s in self.sheets
            ],
            "notes": self.notes,
        }


class BaseQuotationParser(ABC):
    """所有报价文件解析器的统一接口。"""

    file_type: str = "unknown"

    @abstractmethod
    def parse(self, file_path: Path) -> RawFileContent:
        """读取文件并返回统一的原始报价数据结构。

        解析失败时抛出异常，由上层记录错误并标记文件状态。
        """
        raise NotImplementedError
