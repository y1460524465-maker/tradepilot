"""表头映射引擎（TRD 阶段四 / 第十九章：把"单价""报价""Unit Price"等表头转换为统一字段）。

匹配策略：
1. 表头规范化（去空格、去标点、转小写）后与别名精确相等
2. 未命中的表头做子串匹配，取最长别名（保证"报价数量"映射到数量而不是单价）

匹配不上的表头不猜测，原样保留在未映射清单中提示用户。
"""

import re

# 规范字段 -> 常见表头别名（规范化后比较；别名按长度优先匹配）
FIELD_ALIASES: dict[str, list[str]] = {
    "supplier_name": ["供应商名称", "供应商", "suppliername", "supplier", "vendor"],
    "product_name": [
        "产品名称", "产品品名", "品名", "货品名称", "产品", "货品",
        "productname", "product", "itemname", "item", "description",
    ],
    "model": ["产品型号", "型号", "物料号", "料号", "货号", "modelno", "model", "partno", "partnumber"],
    "specification": ["产品规格", "规格型号", "规格说明", "规格", "specification", "spec", "specs"],
    "quantity": ["报价数量", "订购数量", "数量", "qty", "quantity"],
    "unit": ["计量单位", "单位名称", "单位", "unit"],
    "unit_price": [
        "报价单价", "含税单价", "未税单价", "销售单价", "单价",
        "报价", "价格", "unitprice", "price",
    ],
    "currency": ["币种", "币别", "货币", "货币单位", "currency"],
    "tax_rate": ["税率", "taxrate", "tax"],
    "shipping_cost": ["运费", "物流费", "shippingcost", "shipping", "freight"],
    "moq": ["最小起订量", "起订量", "moq"],
    "lead_time_days": ["交货周期", "交货期", "交期", "货期", "货期天", "leadtime"],
    "payment_terms": ["付款条件", "付款方式", "paymentterms", "payment"],
    "valid_until": ["报价有效期", "有效期至", "有效期", "validuntil"],
}

# 需要去除的字符（规范化用）：空格及常见中英文标点
_STRIP_RE = re.compile(r"[\s()（）\[\]【】:：、,，.。·\-_/\\|]+")


def normalize_header(header: str) -> str:
    """表头规范化：去空格与标点、转小写、全角转半角字母数字。"""
    text = (header or "").strip().lower()
    # 全角英数字转半角
    text = text.translate(str.maketrans({chr(f): chr(f - 0xFEE0) for f in range(0xFF01, 0xFF5F)}))
    return _STRIP_RE.sub("", text)


def map_headers(columns: list[str]) -> tuple[dict[str, str], list[str]]:
    """把原始表头映射到规范字段名。

    返回 (mapping, unmapped)：
    - mapping: {原始表头: 规范字段名}，一个字段只取第一个命中的表头
    - unmapped: 未能映射的原始表头列表（提示用户，不猜测）
    """
    mapping: dict[str, str] = {}
    used_fields: set[str] = set()
    unmapped: list[str] = []

    normalized = {col: normalize_header(col) for col in columns}

    # 第一轮：精确相等
    for col, norm in normalized.items():
        if not norm:
            continue
        for field, aliases in FIELD_ALIASES.items():
            if field in used_fields:
                continue
            if norm in aliases:
                mapping[col] = field
                used_fields.add(field)
                break

    # 第二轮：子串匹配，别名最长的优先（避免"报价数量"误判为"报价"）
    for col, norm in normalized.items():
        if col in mapping or not norm:
            continue
        best_field, best_len = None, 0
        for field, aliases in FIELD_ALIASES.items():
            if field in used_fields:
                continue
            for alias in aliases:
                if len(alias) >= 2 and alias in norm and len(alias) > best_len:
                    best_field, best_len = field, len(alias)
        if best_field:
            mapping[col] = best_field
            used_fields.add(best_field)
        else:
            unmapped.append(col)

    return mapping, unmapped
