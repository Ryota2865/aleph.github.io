"""L1 志向層（PLAN §3）— 誰のために書くか（配合比）。「自分」= ALEPHという継続体。

宛先ごとの「書きたさの理由書」を生成し自己選択、intent.md に配合比と
全候補の理由書を記録する（理由書は監査対象, PLAN §3）。

施工: M3（骨格）/ M6（配線）。正典は `tests/test_m6_acceptance.py`。
"""
from __future__ import annotations

from datetime import datetime, timezone

from aleph.core.model_output import parse_model_output, string_map

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# 3宛先の説明（PLAN §3）。プロンプトへ必ず含める。
_DESTINATIONS = (
    ("LLM", "読者はモデル。perplexity・注意の流れ・文脈内学習への作用など、機械的読解に働きかける形式が許される。人間可読性は要求されない。"),
    ("人間", "自然言語の可読性・情動・文化的文脈を重視する。"),
    ("自分", "制作モデル自身の内的一貫性・自己探究。（宛先と公開は別問題。自己宛ては非公開を意味しない——"
             "公開するかは完成後にL7で別途判断する。0.7.15 分離）"),
)


def choose_intent(work, author, policies: dict, *, poetics: str = "") -> str:
    """3宛先の配合比を自己選択し、intent.md に配合比と全候補の理由書を書く（PLAN §3）.

    プロンプトに含める: 3宛先の説明・policies["intent"]["self_definition"]
    （「自分」=ALEPHという継続体の定義）・poetics（あれば, §7.4）。
    author の JSON応答 {"mixture": {宛先: 係数}, "reasons": {宛先: 理由}} を頑健に
    パースする。work.append_decision(layer "L1", ...) を記録する。
    返り値は配合比の文字列表現（例 "人間 0.7 / LLM 0.2 / 自分 0.1"。係数を含める）。
    """
    intent_policy: dict = {}
    if isinstance(policies, dict):
        intent_policy = policies.get("intent", {}) or {}
    self_definition = str(intent_policy.get("self_definition", ""))

    lines = [
        "本作品の読者を誰にするか、3つの宛先（LLM / 人間 / 自分）の配合比を決めてください。",
        "三値ではなく配合比（各宛先の係数、和は1に近いこと）で出力すること。",
        "",
        "【3つの宛先とその含意】",
    ]
    for name, desc in _DESTINATIONS:
        lines.append(f"- {name}: {desc}")
    if self_definition:
        lines += ["", f"【「自分」の定義】", self_definition]
    if poetics:
        lines += ["", f"【詩学（本作が従うべき美の方向）】", poetics]
    lines += [
        "",
        "各宛先について「なぜ書きたいか」の理由書を必ず書き、配合比を出力してください。",
        'JSON {"mixture": {"LLM": 0.x, "人間": 0.x, "自分": 0.x}, '
        '"reasons": {"LLM": "...", "人間": "...", "自分": "..."}} のみを返してください。',
    ]
    prompt = "\n".join(lines)

    response = author(prompt)
    parsed = parse_model_output(
        response,
        schema={
            "mixture": string_map(float, allowed_keys=frozenset({"LLM", "人間", "自分"})),
            "reasons": string_map(str, allowed_keys=frozenset({"LLM", "人間", "自分"})),
        },
    ).require_value()
    mixture = parsed["mixture"]
    reasons = parsed["reasons"]

    # 配合比の文字列表現（係数を含める）
    audience = " / ".join(f"{dest} {coef}" for dest, coef in mixture.items())

    # intent.md: 配合比 + 全候補の理由書（監査対象, PLAN §3）
    md = [
        "# 志向（読者配合比）",
        "",
        "## 配合比",
        "",
    ]
    if mixture:
        for dest, coef in mixture.items():
            md.append(f"- {dest}: {coef}")
    else:
        md.append(f"- {audience}")
    md += ["", "## 各候補の理由書（選択理由・監査対象）", ""]
    if reasons:
        for dest, reason in reasons.items():
            md += [f"### {dest}", "", str(reason), ""]
    else:
        md.append(audience)
        md.append("")
    work.intent.write_text("\n".join(md), encoding="utf-8")

    work.append_decision(
        {
            "ts": _now_iso(),
            "layer": "L1",
            "decision": f"志向配合比: {audience}",
            "reason": "3宛先（LLM/人間/自分）の理由書から自己選択した（PLAN §3）。",
            "decided_by": "author_primary",
        }
    )

    return audience
