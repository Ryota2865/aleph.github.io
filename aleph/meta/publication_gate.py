"""L7 公開判断（PLAN §7.3d）— 完成≠公開。月4作上限・週刊リズム。SHELVEが常態。棚との比較論述を要求

施工: M5. 詳細はPLAN.mdの該当節を正典とする。
"""
from __future__ import annotations

from datetime import datetime, timezone


def _extract_json_object(text: str) -> dict | None:
    """応答中の最初のJSONオブジェクトを頑健に取り出す（他モジュールと同方式・依存回避）."""
    import json

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _ask_publish_intent(author, audience: str) -> tuple[bool, str]:
    """宛先と公開の分離（0.7.15）: 公開意思を著者に明示的に問う。

    自分最大でも自動 SHELVE しない。自己宛ては非公開を意味しない——公開するかは
    著者自身の判断とする。JSON 欠落時は保守的に非公開（棚）へ倒す。
    """
    prompt = (
        "この作品を公開するか判断してください。宛先と公開は別の判断です——"
        "自分に宛てて書いた作品であっても、他者が読むに値すると考えるなら公開しうる"
        "（自己宛ては非公開を意味しません）。逆に、まだ他者に見せるべきでないと考えるなら"
        "非公開を選んでよい。これは規則ではなくあなたの選択です。\n"
        f"想定読者配合: {audience}\n"
        'JSON {"publish": true|false, "reason": "..."} で返してください。'
    )
    response = str(author(prompt))
    parsed = _extract_json_object(response) or {}
    if "publish" in parsed:
        return bool(parsed.get("publish")), str(parsed.get("reason", "")).strip()
    lowered = response.lower()
    if "true" in lowered or "公開する" in response or "公開に値する" in response:
        return True, response.strip()[:200]
    return False, (response.strip()[:200] or "公開意思が判別できないため保守的に非公開とした")


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
    first_publish_ack: bool = True,
) -> dict:
    """公開可否を判定し、L7判断としてdecisions.jsonlに記録する（PLAN §7.3d・§3）.

    宛先と公開の分離（0.7.15、オーナー承認）: 宛先「自分」が最大でも自動 SHELVE しない。
    品質床・月上限・初回承認を満たした上で、公開意思を著者に明示的に問う。SHELVE は規則の
    帰結ではなく著者の選択になる（自己宛ては非公開を意味しない）。
    first_publish_ack=False のときは、他条件が公開可でも SHELVE（初回公開の人間承認。0.7.14）。
    """
    comparison = None

    if not quality_floor_passed:
        decision = "SHELVE"
        reason = "品質の床を通過していないため、公開せず棚に戻す。"
    elif monthly_published >= max_per_month:
        decision = "SHELVE"
        reason = f"月間公開上限 {max_per_month} 作に到達しているため、公開せず保管する。"
    elif not first_publish_ack:
        decision = "SHELVE"
        reason = "初回公開は人間承認待ち（policies.publication.first_publish_ack=false, PLAN §9）。"
    else:
        # 分離（0.7.15）: 宛先に関わらず、公開するかを著者自身に問う。
        publish, intent_reason = _ask_publish_intent(author, audience)
        if not publish:
            decision = "SHELVE"
            reason = f"著者が非公開を選択した（自己宛ては非公開を意味しない。0.7.15）: {intent_reason}"
        else:
            prompt = (
                "以下の作品を公開するため、棚の既公開作と比較して、"
                "なぜ本作が公開に値するかを論述してください。\n\n"
                f"想定読者配合:\n{audience}\n\n"
                "棚の既公開作:\n"
                + ("\n".join(shelf_summaries) if shelf_summaries else "（既公開作なし）")
            )
            comparison = str(author(prompt))
            decision = "PUBLISH"
            reason = "著者が公開を選択し、品質の床・公開数上限を満たし、棚の既公開作との比較論述で公開価値を確認した。"

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
