"""阶段五测试：产品匹配（精确/规则/模糊/冲突禁止合并）与比价计算。"""

import uuid
from decimal import Decimal

import pytest

from tradepilot.app.models.product_match import MatchStatus, MatchType
from tradepilot.app.models.quotation_item import QuotationItem, ReviewStatus
from tradepilot.app.services.comparison_service import Comparability, compute_group
from tradepilot.app.services.matching_service import is_conflict, norm_identity, similarity


# ---------- 身份规范化与冲突判断 ----------


def test_norm_identity_variants():
    assert norm_identity("GB/T 5783") == norm_identity("gb t5783")
    assert norm_identity("M8 X 30") == norm_identity("M8x30")
    assert norm_identity(" 304不锈钢 ") == "304不锈钢"
    assert norm_identity(None) is None
    assert norm_identity("  ") is None


def test_is_conflict_rules():
    # 一方缺失 → 未知，不算冲突
    assert not is_conflict(None, "GB/T 5783")
    assert not is_conflict("GB/T 5783", None)
    # 规范化后一致 → 不冲突
    assert not is_conflict("GB/T 5783", "gb t5783")
    # 都填了且不同 → 冲突
    assert is_conflict("GB/T 5783", "GB/T 5787")
    assert is_conflict("件", "个")


def test_similarity_threshold():
    assert similarity("304不锈钢螺栓", "304不锈钢螺柱") >= 0.85
    assert similarity("不锈钢螺栓", "不锈钢螺母") < 0.85


# ---------- 测试辅助 ----------


def make_item(task_id, supplier, name, model=None, spec=None, unit="件",
              price=Decimal("1.00"), currency="CNY", quantity=Decimal("100")) -> QuotationItem:
    return QuotationItem(
        task_id=task_id,
        supplier_name=supplier,
        product_name=name,
        model=model,
        specification=spec,
        unit=unit,
        unit_price=price,
        currency=currency,
        quantity=quantity,
        review_status=ReviewStatus.CONFIRMED,
    )


def make_task(client) -> str:
    resp = client.post("/api/v1/tasks", json={"task_name": "匹配测试任务"})
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------- 比价计算（纯函数） ----------


def test_compute_group_ranking_and_diff():
    from tradepilot.app.models.product_match import ProductMatch

    group = ProductMatch(
        task_id=uuid.uuid4(), product_name="不锈钢螺栓", model="M8x30",
        match_type=MatchType.EXACT, match_status=MatchStatus.CONFIRMED,
    )
    a = make_item(group.task_id, "华信", "不锈钢螺栓", "M8x30",
                  price=Decimal("0.85"), quantity=Decimal("1000"))
    b = make_item(group.task_id, "宏达", "不锈钢螺栓", "M8x30",
                  price=Decimal("0.82"), quantity=Decimal("1000"))
    result = compute_group(group, [a, b])

    assert result.comparability == Comparability.COMPARABLE
    ranks = {c.supplier_name: c for c in result.items}
    assert ranks["宏达"].rank == 1
    assert ranks["华信"].rank == 2
    assert ranks["华信"].diff_abs == Decimal("0.030000")
    assert ranks["华信"].diff_pct == Decimal("3.66")
    assert ranks["宏达"].estimated_total == Decimal("820.00")
    assert result.best_item_id == ranks["宏达"].item_id


def test_compute_group_currency_mismatch_not_comparable():
    from tradepilot.app.models.product_match import ProductMatch

    group = ProductMatch(
        task_id=uuid.uuid4(), product_name="螺栓",
        match_type=MatchType.EXACT, match_status=MatchStatus.CONFIRMED,
    )
    a = make_item(group.task_id, "A", "螺栓", price=Decimal("1"), currency="CNY")
    b = make_item(group.task_id, "B", "螺栓", price=Decimal("1"), currency="USD")
    result = compute_group(group, [a, b])
    assert result.comparability == Comparability.NOT_COMPARABLE
    assert any("币种不一致" in r for r in result.reasons)
    assert result.best_item_id is None


def test_compute_group_missing_price_blocks():
    from tradepilot.app.models.product_match import ProductMatch

    group = ProductMatch(
        task_id=uuid.uuid4(), product_name="螺栓",
        match_type=MatchType.EXACT, match_status=MatchStatus.CONFIRMED,
    )
    a = make_item(group.task_id, "A", "螺栓", price=Decimal("1"))
    b = make_item(group.task_id, "B", "螺栓", price=None)
    result = compute_group(group, [a, b])
    assert result.comparability == Comparability.NOT_COMPARABLE
    assert any("缺少单价" in c.issues[0] for c in result.items if c.issues)


# ---------- 匹配接口（E2E） ----------


def seed_items(Session, task_id: str, items: list[QuotationItem]) -> None:
    db = Session()
    try:
        for it in items:
            it.task_id = uuid.UUID(task_id)
            db.add(it)
        db.commit()
    finally:
        db.close()


def test_match_exact_group_and_comparison_api(client, session_factory):
    task_id = make_task(client)
    seed_items(
        session_factory,
        task_id,
        [
            make_item(None, "华信五金", "不锈钢螺栓", "M8x30", "GB/T 5783",
                      price=Decimal("0.85"), quantity=Decimal("1000")),
            make_item(None, "宏达标准件", "不锈钢螺栓", "M8X30", "gbt5783",
                      price=Decimal("0.82"), quantity=Decimal("1000")),
        ],
    )
    summary = client.post(f"/api/v1/tasks/{task_id}/match").json()
    assert summary["groups"]["exact"] == 1
    assert summary["total_items"] == 2

    report = client.get(f"/api/v1/tasks/{task_id}/matches").json()
    assert report["comparable_groups"] == 1
    group = report["groups"][0]
    assert group["match_type"] == "exact"
    assert group["best_item_id"] is not None
    best = next(c for c in group["items"] if c["item_id"] == group["best_item_id"])
    assert Decimal(best["unit_price"]) == Decimal("0.82")


def test_spec_conflict_prevents_auto_merge(client, session_factory):
    task_id = make_task(client)
    seed_items(
        session_factory,
        task_id,
        [
            make_item(None, "A司", "六角螺栓", "M8", "GB/T 5783", price=Decimal("1")),
            make_item(None, "B司", "六角螺栓", "M8", "GB/T 5787", price=Decimal("2")),
        ],
    )
    summary = client.post(f"/api/v1/tasks/{task_id}/match").json()
    # 不允许合并成一个 exact/rule 组；各自单独成组并说明原因
    assert summary["groups"]["exact"] == 0
    assert summary["groups"]["rule"] == 0
    report = client.get(f"/api/v1/tasks/{task_id}/matches").json()
    assert all(g["item_count"] == 1 for g in report["groups"])
    assert any("冲突" in (g["note"] or "") for g in report["groups"])


def test_fuzzy_group_needs_manual_confirm(client, session_factory):
    task_id = make_task(client)
    seed_items(
        session_factory,
        task_id,
        [
            make_item(None, "A司", "304不锈钢螺栓", "M8", price=Decimal("1.10")),
            make_item(None, "B司", "304不锈钢螺柱", "M8", price=Decimal("1.05")),
        ],
    )
    summary = client.post(f"/api/v1/tasks/{task_id}/match").json()
    assert summary["groups"]["fuzzy"] == 1

    report = client.get(f"/api/v1/tasks/{task_id}/matches").json()
    group = report["groups"][0]
    assert group["match_type"] == "fuzzy"
    assert group["match_status"] == "pending_review"
    assert group["comparability"] == "needs_review"

    # 人工确认后状态更新
    patched = client.patch(
        f"/api/v1/matches/{group['match_id']}", json={"match_status": "confirmed"}
    )
    assert patched.status_code == 200
    assert patched.json()["match_status"] == "confirmed"


def test_rule_group_unit_conflict_stays_apart(client, session_factory):
    """名称+型号一致但单位冲突 → 不自动合并。"""
    task_id = make_task(client)
    seed_items(
        session_factory,
        task_id,
        [
            make_item(None, "A司", "平垫圈", "M8", unit="件", price=Decimal("0.08")),
            make_item(None, "B司", "平垫圈", "M8", unit="包", price=Decimal("8.00")),
        ],
    )
    summary = client.post(f"/api/v1/tasks/{task_id}/match").json()
    assert summary["groups"]["rule"] == 0
    assert summary["groups"]["exact"] == 0


def test_match_is_idempotent(client, session_factory):
    task_id = make_task(client)
    seed_items(
        session_factory,
        task_id,
        [
            make_item(None, "A司", "螺栓", "M8", price=Decimal("1")),
            make_item(None, "B司", "螺栓", "M8", price=Decimal("2")),
        ],
    )
    first = client.post(f"/api/v1/tasks/{task_id}/match").json()
    second = client.post(f"/api/v1/tasks/{task_id}/match").json()
    assert first == second
    report = client.get(f"/api/v1/tasks/{task_id}/matches").json()
    assert report["total_groups"] == sum(first["groups"].values())
    # 重跑后明细仍正确挂在新组上
    assert sum(g["item_count"] for g in report["groups"]) == 2


def test_match_unknown_task_404(client):
    resp = client.post(
        f"/api/v1/tasks/{uuid.uuid4()}/match"
    )
    assert resp.status_code == 404


def test_patch_match_status_invalid_value_422(client, session_factory):
    task_id = make_task(client)
    seed_items(session_factory, task_id, [make_item(None, "A", "螺栓", price=Decimal("1"))])
    client.post(f"/api/v1/tasks/{task_id}/match")
    report = client.get(f"/api/v1/tasks/{task_id}/matches").json()
    match_id = report["groups"][0]["match_id"]
    resp = client.patch(f"/api/v1/matches/{match_id}", json={"match_status": "whatever"})
    assert resp.status_code == 422
