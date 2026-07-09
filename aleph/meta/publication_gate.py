"""L7 公開判断（PLAN §7.3d）— 完成≠公開。月4作上限・週刊リズム。SHELVEが常態。棚との比較論述を要求

施工: M5. 詳細はPLAN.mdの該当節を正典とする。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone


def _audience_weights(audience: str) -> dict[str, float]:
    weights: dict[str, float] = {}
    for label, value in re.findall(r"([^/\n,、]+?)\s*[=:：]?\s*([0-9]+(?:\.[0-9]+)?)", audience):
        label = label.strip()
        try:
            weights[label] = float(value)
        except ValueError:
            continue
    return weights


def _self_is_primary_audience(audience: str) -> bool:
    weights = _audience_weights(audience)
    self_weights = [value for label, value in weights.items() if "自分" in label]
    if not self_weights:
        return False

    self_weight = max(self_weights)
    other_weights = [value for label, value in weights.items() if "自分" not in label]
    if not other_weights:
        return True
    return self_weight >= 0.5 or self_weight > max(other_weights)


def decide_publication(
    work,
    *,
    audience: str,
    quality_floor_passed: bool,
    monthly_published: int,
    max_per_month: int,
    shelf_summaries: list[str],
    author,
    decided_by: str,
) -> dict:
    """公開可否を判定し、L7判断としてdecisions.jsonlに記録する（PLAN §7.3d）."""
    comparison = None

    if _self_is_primary_audience(audience):
        decision = "SHELVE"
        reason = "宛先配合で「自分」が最大のため、公開を前提とせず保管する（PLAN §3）。"
    elif not quality_floor_passed:
        decision = "SHELVE"
        reason = "品質の床を通過していないため、公開せず棚に戻す。"
    elif monthly_published >= max_per_month:
        decision = "SHELVE"
        reason = f"月間公開上限 {max_per_month} 作に到達しているため、公開せず保管する。"
    else:
        prompt = (
            "以下の作品を公開するか判断するため、棚の既公開作と比較して、"
            "なぜ本作が公開に値するかを論述してください。\n\n"
            f"想定読者配合:\n{audience}\n\n"
            "棚の既公開作:\n"
            + ("\n".join(shelf_summaries) if shelf_summaries else "（既公開作なし）")
        )
        comparison = str(author(prompt))
        decision = "PUBLISH"
        reason = "品質の床と公開数上限を満たし、棚の既公開作との比較論述で公開価値を確認した。"

    work.append_decision(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "layer": "L7",
            "decision": f"publication:{decision}",
            "reason": reason,
            "decided_by": decided_by,
        }
    )

    return {"decision": decision, "reason": reason, "comparison": comparison}
