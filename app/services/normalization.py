"""数值 / 币种 / 日期规范化（TRD 阶段四：统一币种、日期和数值格式）。

原则：无法确定就返回 None 并让上层记录告警进人工复核，不猜测填充。
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# 常见币种表达（规范化后小写比较）
CURRENCY_ALIASES: dict[str, str] = {
    "cny": "CNY", "rmb": "CNY", "人民币": "CNY", "元": "CNY", "￥": "CNY", "¥": "CNY", "块": "CNY",
    "usd": "USD", "美元": "USD", "美金": "USD", "$": "USD", "us$": "USD",
    "eur": "EUR", "欧元": "EUR", "€": "EUR",
    "jpy": "JPY", "日元": "JPY", "日圆": "JPY", "円": "JPY",
    "hkd": "HKD", "港币": "HKD", "港元": "HKD",
}

# 数值里的干扰字符：货币符号、千分位逗号、空格、全角符号、人民币"元"后缀
_NUMERIC_CLEAN_RE = re.compile(r"[¥￥$€£,\s，元圆]")

_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日", "%d/%m/%Y", "%m/%d/%Y")


def clean_str(value) -> str | None:
    """通用字符串清洗：去首尾空白与引号，空值归 None。"""
    if value is None:
        return None
    text = str(value).strip().strip("'\"").strip()
    return text or None


def parse_decimal(value) -> Decimal | None:
    """解析金额/数量/税率。支持 '1,234.50'、'¥85.0'、'0.85元' 等表达；失败返回 None。"""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = _NUMERIC_CLEAN_RE.sub("", str(value).strip())
    if not text:
        return None
    try:
        result = Decimal(text)
    except InvalidOperation:
        return None
    return result


def parse_int(value) -> int | None:
    """解析整数（交货周期等）。'15天'、'15 天' 均可。"""
    number = parse_decimal(value)
    if number is None:
        return None
    return int(number)


def parse_currency(value) -> str | None:
    """解析币种：'CNY'、'cny'、'人民币'、'¥'、'元' 均可；未知币种返回 None。"""
    text = clean_str(value)
    if not text:
        return None
    return CURRENCY_ALIASES.get(text.strip().lower()) or CURRENCY_ALIASES.get(text.strip())


def parse_date(value) -> date | None:
    """解析日期：datetime/date 实例直接取值；字符串尝试常见格式（含 2026年12月31日）。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = clean_str(value)
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None
