"""产品匹配（TRD 8.2 / 阶段五：把任务内报价明细分成"同一产品"的可比组）。

三级匹配，从严到松：
1. 精确匹配：型号+规格+单位 完全一致 → 自动合并（exact / confirmed）
2. 规则匹配：规范化后 产品名称+型号 一致，且规格/单位无冲突 → 自动合并（rule / confirmed）
3. 模糊匹配：名称高度相似但证据不足或有冲突 → 仅聚成待确认组（fuzzy / pending_review）

铁律（TRD 第十/十一章）：
- 规格冲突（双方都填了且不同）禁止自动合并；
- 模糊匹配只是辅助证据，必须人工确认后才能参与正式比价；
- 所有合并决策可解释（match_evidence 记录原因）。
"""

import re
import unicodedata
import uuid
from difflib import SequenceMatcher

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tradepilot.app.models.product_match import MatchStatus, MatchType, ProductMatch
from tradepilot.app.models.quotation_item import QuotationItem

# 模糊匹配的相似度门槛（保守值，只用于生成"疑似"提示）
FUZZY_THRESHOLD = 0.85

# 身份规范化时剔除的干扰字符：空白、连字符、斜杠、括号、量词等
_IDENTITY_CLEAN_RE = re.compile(r"[\s\-—_/\\（）()【】\[\]、,，。.·:：*×xX\"]+")


def norm_identity(value: str | None) -> str | None:
    """产品身份文本规范化：全角转半角、小写、去干扰字符。

    'GB/T 5783' 与 'gbt5783'、'M8 x 30' 与 'M8X30' 归一。
    """
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    text = _IDENTITY_CLEAN_RE.sub("", text)
    return text or None


def is_conflict(a: str | None, b: str | None) -> bool:
    """双方都填了且规范化后不同 → 冲突；一方缺失 → 未知，不算冲突。"""
    na, nb = norm_identity(a), norm_identity(b)
    return na is not None and nb is not None and na != nb


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


class MatchingService:
    def __init__(self, db: Session):
        self.db = db

    def run_match(self, task_id: uuid.UUID) -> dict:
        """对任务内全部报价明细执行匹配（幂等：重跑先清空旧分组）。"""
        items = self.db.scalars(
            select(QuotationItem)
            .where(QuotationItem.task_id == task_id)
            .order_by(QuotationItem.created_at.asc())
        ).all()

        # 幂等：清空旧的分组归属
        self.db.execute(delete(ProductMatch).where(ProductMatch.task_id == task_id))
        for item in items:
            item.match_id = None
        self.db.flush()

        groups = self._build_groups(items)
        summary = {"exact": 0, "rule": 0, "fuzzy": 0, "single": 0}
        for members, match_type, evidence, note in groups:
            status = (
                MatchStatus.CONFIRMED if match_type in (MatchType.EXACT, MatchType.RULE)
                else MatchStatus.PENDING_REVIEW
            )
            summary[match_type.value] += 1
            self._create_group(task_id, members, match_type, status, evidence, note)
        self.db.commit()
        return summary

    # ------------------------------------------------------------------ 分组

    def _build_groups(self, items: list[QuotationItem]) -> list[tuple]:
        """返回 [(members, MatchType, evidence, note), ...]，覆盖全部明细。"""
        results: list[tuple] = []
        unmatched = [it for it in items if not norm_identity(it.product_name)]

        # 第 1 级：精确匹配（四要素齐全且一致）
        exact_buckets: dict[tuple, list[QuotationItem]] = {}
        remaining: list[QuotationItem] = []
        for it in items:
            if norm_identity(it.product_name) is None:
                continue
            key = (
                norm_identity(it.product_name),
                norm_identity(it.model),
                norm_identity(it.specification),
                norm_identity(it.unit),
            )
            if all(key[1:]):  # 型号、规格、单位必须齐全才算精确
                exact_buckets.setdefault(key, []).append(it)
            else:
                remaining.append(it)
        for key, members in exact_buckets.items():
            if len(members) > 1:
                evidence = {
                    "reason": "型号、规格、计量单位完全一致",
                    "key": {"product": key[0], "model": key[1], "spec": key[2], "unit": key[3]},
                }
                results.append((members, MatchType.EXACT, evidence, None))
            else:
                # 只有自己一个的四要素齐全明细，交给规则级继续找可比对象
                remaining.extend(members)

        # 第 2 级：规则匹配（名称+型号一致，且组内规格/单位无冲突）
        rule_buckets: dict[tuple, list[QuotationItem]] = {}
        after_rule: list[QuotationItem] = []
        for it in remaining:
            name, model = norm_identity(it.product_name), norm_identity(it.model)
            if name and model:
                rule_buckets.setdefault((name, model), []).append(it)
            else:
                after_rule.append(it)
        for (name, model), members in rule_buckets.items():
            conflict_free, conflict_items = self._partition_conflict_free(members)
            if len(conflict_free) > 1:
                evidence = {
                    "reason": "规范化后产品名称与型号一致，且规格/单位无冲突",
                    "key": {"product": name, "model": model},
                }
                results.append((conflict_free, MatchType.RULE, evidence, None))
            else:
                after_rule.extend(conflict_free)
            for it in conflict_items:
                it_spec_note = "与同名称型号的其它报价规格冲突，禁止自动合并"
                results.append(
                    (
                        [it],
                        MatchType.SINGLE,
                        {"reason": it_spec_note},
                        it_spec_note,
                    )
                )

        # 第 3 级：模糊匹配（仅对剩余单条、有名称的明细，生成"疑似"待确认组）
        fuzzy_used: set[int] = set()
        fuzzy_buckets: dict[int, list[QuotationItem]] = {}
        fuzzy_notes: dict[int, str] = {}
        singles = [it for it in after_rule if norm_identity(it.product_name)]
        for i, a in enumerate(singles):
            if id(a) in fuzzy_used:
                continue
            bucket = [a]
            notes = []
            for b in singles[i + 1:]:
                if id(b) in fuzzy_used:
                    continue
                sim = similarity(
                    norm_identity(a.product_name) + (norm_identity(a.model) or ""),
                    norm_identity(b.product_name) + (norm_identity(b.model) or ""),
                )
                if sim >= FUZZY_THRESHOLD:
                    conflict_desc = self._describe_conflicts(a, b)
                    if conflict_desc:
                        notes.append(f"与「{b.product_name}」相似度 {sim:.2f}，但{conflict_desc}")
                        continue  # 有冲突的连模糊组都不进，保持独立
                    bucket.append(b)
                    fuzzy_used.add(id(b))
                    notes.append(f"与「{b.product_name}」相似度 {sim:.2f}")
            if len(bucket) > 1:
                for m in bucket:
                    fuzzy_used.add(id(m))
                gid = len(fuzzy_buckets)
                fuzzy_buckets[gid] = bucket
                fuzzy_notes[gid] = "；".join(notes)

        for gid, members in fuzzy_buckets.items():
            results.append(
                (
                    members,
                    MatchType.FUZZY,
                    {"reason": "名称高度相似但证据不足，需人工确认", "details": fuzzy_notes[gid]},
                    "疑似同一产品，请人工确认后再比价",
                )
            )
        after_rule = [it for it in after_rule if id(it) not in fuzzy_used]

        # 其余：单独成组
        for it in after_rule + unmatched:
            note = None if norm_identity(it.product_name) else "缺少产品名称，无法参与匹配"
            results.append(([it], MatchType.SINGLE, {"reason": "没有找到可比对象"}, note))
        return results

    def _partition_conflict_free(self, members: list[QuotationItem]) -> tuple[list, list]:
        """在名称+型号相同的明细里，把与代表项规格/单位冲突的挑出来（不自动合并）。"""
        representative = members[0]
        conflict_items = [
            it
            for it in members[1:]
            if is_conflict(it.specification, representative.specification)
            or is_conflict(it.unit, representative.unit)
        ]
        conflict_free = [it for it in members if it not in conflict_items]
        return conflict_free, conflict_items

    def _describe_conflicts(self, a: QuotationItem, b: QuotationItem) -> str:
        parts = []
        if is_conflict(a.specification, b.specification):
            parts.append(f"规格冲突（{a.specification} vs {b.specification}）")
        if is_conflict(a.unit, b.unit):
            parts.append(f"单位冲突（{a.unit} vs {b.unit}）")
        return "、".join(parts)

    # ------------------------------------------------------------------ 入库

    def _create_group(
        self,
        task_id: uuid.UUID,
        members: list[QuotationItem],
        match_type: MatchType,
        match_status: MatchStatus,
        evidence: dict,
        note: str | None,
    ) -> ProductMatch:
        group = ProductMatch(
            task_id=task_id,
            product_name=members[0].product_name,
            model=members[0].model,
            specification=members[0].specification,
            unit=members[0].unit,
            match_type=match_type,
            match_status=match_status,
            item_count=len(members),
            match_evidence=evidence,
            note=note,
        )
        self.db.add(group)
        self.db.flush()
        for it in members:
            it.match_id = group.id
        return group
