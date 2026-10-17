"""解析器注册表：按文件类型选择解析器。"""

from pathlib import Path

from app.models.uploaded_file import FileTypeEnum
from app.parsers.base import BaseQuotationParser, RawFileContent
from app.parsers.csv_parser import CsvQuotationParser
from app.parsers.excel_parser import ExcelQuotationParser
from app.parsers.pdf_parser import PdfQuotationParser

_PARSERS: dict[FileTypeEnum, BaseQuotationParser] = {
    FileTypeEnum.XLSX: ExcelQuotationParser(),
    FileTypeEnum.CSV: CsvQuotationParser(),
    FileTypeEnum.PDF: PdfQuotationParser(),
}


def get_parser(file_type: FileTypeEnum) -> BaseQuotationParser:
    return _PARSERS[file_type]


def parse_file(file_type: FileTypeEnum, file_path: Path) -> RawFileContent:
    return get_parser(file_type).parse(file_path)
