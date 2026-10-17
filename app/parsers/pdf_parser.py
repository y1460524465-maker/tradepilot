"""文本型 PDF 解析器（PyMuPDF：优先提取表格，无表格时提取文本行预览）。

第一版不承诺支持扫描件和复杂排版（TRD 6.1）。
"""

from pathlib import Path

import fitz  # PyMuPDF

from app.parsers.base import BaseQuotationParser, RawFileContent, RawSheet

PREVIEW_ROWS = 50


class PdfQuotationParser(BaseQuotationParser):
    file_type = "pdf"

    def parse(self, file_path: Path) -> RawFileContent:
        result = RawFileContent(file_type=self.file_type)

        with fitz.open(file_path) as doc:
            for page_number, page in enumerate(doc, start=1):
                tables = page.find_tables()
                if tables and tables.tables:
                    for t_index, table in enumerate(tables.tables, start=1):
                        data = table.extract()
                        if not data:
                            continue
                        header = [str(c).strip() if c else "" for c in data[0]]
                        rows = data[1:]
                        result.sheets.append(
                            RawSheet(
                                name=f"第{page_number}页-表{t_index}",
                                columns=header,
                                row_count=len(rows),
                                preview_rows=rows[:PREVIEW_ROWS],
                            )
                        )
                else:
                    text = page.get_text("text").strip()
                    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                    result.sheets.append(
                        RawSheet(
                            name=f"第{page_number}页-文本",
                            row_count=len(lines),
                            preview_rows=[[ln] for ln in lines[:PREVIEW_ROWS]],
                        )
                    )
                    if page_number == 1 and not lines:
                        result.notes.append("PDF 第一页没有可提取的文本，可能是扫描件")
        return result
