"""L7 人間協働判断（PLAN §7.3b）— 呼ぶ/呼ばない両方の理由を記録。協働を選んだ作品のみtaste錨を要請できる(§14.3-6)

施工: M5。既定は自律。倫理的リスク・価値観の岐路・コミュニティ公開規範のいずれかで人間を呼ぶ。
"""
from __future__ import annotations

from datetime import datetime, timezone


def decide_collaboration(work, context: dict, *, decided_by: str) -> dict:
    """人間を呼ぶか否かを判定し、どちらの結果でも decisions.jsonl (layer L7) に記録する（PLAN §7.3b）."""
    ethical_flags = context.get("ethical_flags") or []
    value_crossroads = bool(context.get("value_crossroads"))
    community_publication = bool(context.get("community_publication"))

    call_human = bool(ethical_flags) or value_crossroads or community_publication

    if call_human:
        reasons = []
        if ethical_flags:
            reasons.append("倫理的リスクをL6が検知: " + ", ".join(str(flag) for flag in ethical_flags))
        if value_crossroads:
            reasons.append("判断が価値観の岐路でintentから導出できない")
        if community_publication:
            reasons.append("公開先が人間コミュニティで規範への適合確認が必要")
        reason = "; ".join(reasons)
    else:
        reason = (
            "倫理的リスク・価値観の岐路・コミュニティ公開規範のいずれにも該当しないため、"
            "自律判断のまま継続する"
        )

    work.append_decision(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "layer": "L7",
            "decision": "call_human" if call_human else "no_call",
            "reason": reason,
            "decided_by": decided_by,
        }
    )

    return {"call_human": call_human, "reason": reason}
