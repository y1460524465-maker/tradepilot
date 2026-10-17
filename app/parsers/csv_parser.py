"""CSV 解析器（自动尝试常见编码：utf-8-sig / gbk / latin-1）。"""

from pathlib import Path

import pandas as pd

from tradepilot.app.parsers.base import BaseQuotationParser, RawFileContent, RawSheet

ENCODINGS = ("utf-8-sig", "gbk", "latin-1")


class CsvQuotationParser(BaseQuotationParser):
    file_type = "csv"

    def parse(self, file_path: Path) -> RawFileContent:
        result = RawFileContent(file_type=self.file_type)

        df = None
        errors: list[str] = []
        for enc in ENCODINGS:
            try:
                df = pd.read_csv(file_path, dtype=object, encoding=enc)
                break
            except (UnicodeDecodeError, pd.errors.ParserError) as e:
                errors.append(f"{enc}: {e}")
        if df is None:
            raise ValueError("CSV 解析失败，尝试的编码均无法读取：" + "; ".join(errors))

        df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
        if not df.empty:
            columns = [str(c).strip() for c in df.columns]
            rows = df.where(df.notna(), None).values.tolist()
            result.sheets.append(
                RawSheet(name="csv", columns=columns, row_count=len(rows), rows=rows)
            )
        return result
