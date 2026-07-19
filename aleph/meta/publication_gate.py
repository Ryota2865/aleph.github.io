"""L7 公開判断（PLAN §7.3d）— 完成≠公開。月4作上限・週刊リズム。SHELVEが常態。棚との比較論述を要求

施工: M5. 詳細はPLAN.mdの該当節を正典とする。
"""
from __future__ import annotations

from datetime import datetime, timezone

from aleph.core.model_output import parse_model_output
from aleph.core.evaluation import EvaluationPacket


def _coerce_publish(value) -> bool | None:
    """publish 値を頑健に真偽へ。文字列 "false"/"no"/"0" を True にしない（監査 finding 2）."""
    return value if type(value) is bool else None


def _best_draft_excerpt(work, limit: int = 6000) -> str:
    """公開判断のため作品本文の抜粋を得る（最高スコア版→最新版）。無ければ空。"""
    try:
        import json

        best = None
        traj = work.dir / "reviews" / "trajectory.jsonl"
        if traj.exists():
            rows = [json.loads(l) for l in traj.read_text(encoding="utf-8").splitlines() if l.strip()]
            if rows:
                best = int(max(rows, key=lambda r: float(r.get("mean_score", 0.0))).get("version", 0))
        if not best:
            best = work.latest_draft_version()
        if best and work.draft_path(best).exists():
            text = work.draft_path(best).read_text(encoding="utf-8")
            return text if len(text) <= limit else text[: limit * 2 // 3] + "\n……\n" + text[-limit // 3:]
    except Exception:
        pass
    return ""


def _ask_publish_intent(author, audience: str, work_excerpt: str = "") -> tuple[bool, str]:
    """宛先と公開の分離（0.7.15）: 公開意思を著者に明示的に問う。

    自分最大でも自動 SHELVE しない。自己宛ては非公開を意味しない——公開するかは
    著者自身の判断とする。作品本文の抜粋を必ず渡す（監査 finding 1: 内容非依存を防ぐ）。
    JSON 欠落や判別不能時は保守的に非公開（棚）へ倒す（公開は不可逆寄りのため安全側）。
    """
    lines = [
        "以下の作品を公開するか判断してください。宛先と公開は別の判断です——",
        "自分に宛てて書いた作品であっても、他者が読むに値すると考えるなら公開しうる",
        "（自己宛ては非公開を意味しません）。逆に、まだ他者に見せるべきでないと考えるなら",
        "非公開を選んでよい。これは規則ではなくあなたの選択です。",
        "注記: ここでの「非公開」は「見えなくする」ことではありません。この作品は",
        "選んだ結果に関わらず、制作記録全体（基準書・決定ログ・草稿・査読）が",
        "このリポジトリの深層アーカイブとして残ります。ここで問うているのは、",
        "読者向けの完成品として提示するかどうかです。",
        f"想定読者配合: {audience}",
    ]
    if work_excerpt:
        lines += ["", "作品（抜粋）:", work_excerpt]
    lines.append('JSON {"publish": true|false, "reason": "..."} で返してください。')
    response = str(author("\n".join(lines)))
    output = parse_model_output(response, schema={"publish": bool, "reason": str})
    if output.ok:
        return output.value["publish"], output.value["reason"].strip()
    # フォールバック（JSON欠落/判別不能）: 否定を優先し、明確な肯定のみ True。
    if "非公開" in response or "公開しない" in response or "公開すべきでない" in response:
        return False, response.strip()[:200]
    if "公開する" in response or "公開に値する" in response:
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
    budget_exhausted: bool = False,
    packet: EvaluationPacket | None = None,
) -> dict:
    """公開可否を判定し、L7判断としてdecisions.jsonlに記録する（PLAN §7.3d・§3）.

    宛先と公開の分離（0.7.15、オーナー承認）: 宛先「自分」が最大でも自動 SHELVE しない。
    品質床・月上限・初回承認を満たした上で、公開意思を著者に明示的に問う。SHELVE は規則の
    帰結ではなく著者の選択になる（自己宛ては非公開を意味しない）。
    first_publish_ack=False のときは、他条件が公開可でも SHELVE（初回公開の人間承認。0.7.14）。
    """
    if packet is not None:
        packet.validate()
    comparison = None

    if budget_exhausted:
        decision = "SHELVE"
        reason = "API予算残額が追加の公開意思確認に足りないため、再課金せず棚に戻す。"
    elif not quality_floor_passed:
        decision = "SHELVE"
        reason = "品質の床を通過していないため、公開せず棚に戻す。"
    elif monthly_published >= max_per_month:
        decision = "SHELVE"
        reason = f"月間公開上限 {max_per_month} 作に到達しているため、公開せず保管する。"
    elif not first_publish_ack:
        decision = "SHELVE"
        reason = "初回公開は人間承認待ち（policies.publication.first_publish_ack=false, PLAN §9）。"
    else:
        # 分離（0.7.15）: 宛先に関わらず、公開するかを著者自身に問う（本文抜粋つき, 監査 finding 1）。
        publish, intent_reason = _ask_publish_intent(author, audience, _best_draft_excerpt(work))
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

    record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "layer": "L7",
            "decision": f"publication:{decision}",
            "reason": reason,
            "decided_by": decided_by,
        }
    if packet is not None:
        record["evaluation_packet_hash"] = packet.hash
        record["effective_constraints_hash"] = packet.effective_constraints_hash
    work.append_decision(record)

    result = {"decision": decision, "reason": reason, "comparison": comparison}
    if packet is not None:
        result["evaluation_packet_hash"] = packet.hash
        result["effective_constraints_hash"] = packet.effective_constraints_hash
    return result
