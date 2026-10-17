"""报价数据结构测试：必填校验、Decimal 金额、枚举约束（TRD 17 测试要求）。"""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tradepilot.app.schemas.quotation import (
    CurrencyCode,
    ExtractionMethod,
    QuotationItemCreate,
    QuotationItemRead,
)


def make_payload(**overrides):
    payload = {
        "supplier_name": "供应商A",
        "product_name": "不锈钢螺栓",
        "model": "M8x30",
        "quantity": "1000",
        "unit": "件",
        "unit_price": "0.85",
        "currency": "CNY",
    }
    payload.update(overrides)
    return payload


def test_valid_item_parses_decimal_price():
    item = QuotationItemCreate(**make_payload())
    assert item.unit_price == Decimal("0.85")
    assert item.currency == CurrencyCode.CNY
    assert item.extraction_method == ExtractionMethod.RULE


def test_missing_required_price_fails():
    payload = make_payload()
    payload.pop("unit_price")
    with pytest.raises(ValidationError):
        QuotationItemCreate(**payload)


def test_missing_currency_fails():
    payload = make_payload()
    payload.pop("currency")
    with pytest.raises(ValidationError):
        QuotationItemCreate(**payload)


def test_negative_price_rejected():
    with pytest.raises(ValidationError):
        QuotationItemCreate(**make_payload(unit_price="-1"))


def test_invalid_currency_rejected():
    with pytest.raises(ValidationError):
        QuotationItemCreate(**make_payload(currency="XXX"))


def test_tax_rate_must_be_between_0_and_1():
    with pytest.raises(ValidationError):
        QuotationItemCreate(**make_payload(tax_rate="13"))
    item = QuotationItemCreate(**make_payload(tax_rate="0.13"))
    assert item.tax_rate == Decimal("0.13")


def test_read_defaults_to_pending_review():
    item = QuotationItemRead(
        id="11111111-1111-1111-1111-111111111111",
        **make_payload(),
        valid_until=date(2026, 12, 31),
    )
    assert item.review_status.value == "pending_review"
    assert item.valid_until == date(2026, 12, 31)
