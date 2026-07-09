"""L3 アルスコンビナトリア（PLAN §5.2）— 空きセル表から通常あり得ない組合せを系統生成

軸（主題・形式・視点…）の直積から、既存の占有セルを除いた空きセルだけを列挙する
（ランダム生成ではない）。各組合せに scout で実現可能性・面白さの見立てを付け、
素材カード化する。

施工: M2. 詳細はPLAN.mdの該当節を正典とする。
"""
from __future__ import annotations

import itertools

from aleph.explore.niche import _extract_json_object


def generate_combinations(axes: dict[str, list[str]], existing: set[tuple]) -> list[dict]:
    """軸の直積から既存タプル（axesキー順）を除いた空きセルを列挙する（PLAN §5.2）."""
    keys = list(axes.keys())
    combos = []
    for values in itertools.product(*(axes[key] for key in keys)):
        if values in existing:
            continue
        combos.append(dict(zip(keys, values)))
    return combos


def assess(combos: list[dict], scout) -> list[dict]:
    """各組合せに scout の実現可能性・面白さの見立てを付ける（PLAN §5.2）.

    scout応答のJSONパースに失敗した場合は feasibility=0.5, interest=0.5,
    rationale=応答原文とする。
    """
    assessed = []
    for combo in combos:
        description = "×".join(f"{axis}:{value}" for axis, value in combo.items())
        prompt = (
            "次の通常あり得ない組合せについて、実現可能性と面白さを見立ててください。"
            '結果は JSON {"feasibility": 0.0, "interest": 0.0, "rationale": "..."} だけで返してください。\n'
            f"組合せ: {description}"
        )
        response = scout(prompt)
        parsed = _extract_json_object(response)
        if parsed is None:
            feasibility, interest, rationale = 0.5, 0.5, response.strip()
        else:
            try:
                feasibility = float(parsed.get("feasibility", 0.5))
            except (TypeError, ValueError):
                feasibility = 0.5
            try:
                interest = float(parsed.get("interest", 0.5))
            except (TypeError, ValueError):
                interest = 0.5
            rationale = str(parsed.get("rationale", response.strip()))
        assessed.append({**combo, "feasibility": feasibility, "interest": interest, "rationale": rationale})
    return assessed


def to_material_cards(assessed: list[dict]) -> list[dict]:
    """見立て済み組合せを素材カード（PLAN §5冒頭）に統一する."""
    reserved = {"feasibility", "interest", "rationale"}
    cards = []
    for item in assessed:
        combo = {k: v for k, v in item.items() if k not in reserved}
        description = "×".join(f"{axis}:{value}" for axis, value in combo.items())
        content = description
        rationale = item.get("rationale")
        if rationale:
            content += f"\n[見立て] {rationale}"
        card = {
            "content": content,
            "source": combo,
            "method": "combinator",
            "tags": ["combination"],
            "provenance": {
                "feasibility": item.get("feasibility"),
                "interest": item.get("interest"),
            },
        }
        cards.append(card)
    return cards
