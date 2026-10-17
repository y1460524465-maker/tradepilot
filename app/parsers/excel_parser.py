"""Excel 解析器（.xlsx，OpenPyXL 引擎）。"""

from pathlib import Path

import pandas as pd

from tradepilot.app.parsers.base import BaseQuotationParser, RawFileContent, RawSheet



class ExcelQuotationParser(BaseQuotationParser):
    file_type = "xlsx"

    def parse(self, file_path: Path) -> RawFileContent:
        # sheet_name=None 读全部工作表；dtype=object 保留原始内容，不做隐式类型转换
        sheets = pd.read_excel(file_path, sheet_name=None, dtype=object)
        result = RawFileContent(file_type=self.file_type)

        for name, df in sheets.items():
            df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")  # 去空行空列（TRD 阶段三）
            if df.empty:
                result.sheets.append(RawSheet(name=str(name), row_count=0))
                continue

            columns = [str(c).strip() for c in df.columns]
            rows = df.where(df.notna(), None).values.tolist()
            result.sheets.append(
                RawSheet(name=str(name), columns=columns, row_count=len(rows), rows=rows)
            )
        return result
