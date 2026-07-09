"""L5 執筆（PLAN §6.2）— 部分執筆→結合→全体通読。階層文脈方式。意図的断絶は保存.

施工: M3。正典は `tests/test_m3_acceptance.py`。
部分執筆の各プロンプトには (a) 宛先 (b) これまでの要約 (c) 直前セクション全文
(d) 構成上の現在位置 (e) 文体方針 を必ず含める（PLAN §6.2）。
全体通読パスでは縫い目ごとに「平滑化」を依頼するが、intentional_break=True の
縫い目（前partが担う）はスキップし、意図的な断絶を保存する。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from aleph.compose.generate import derive_criteria, evolve, generate_proposals

Author = Callable[[str], str]
Critic = Callable[[str], str]

_SUMMARY_CHARS = 400
_SEAM_CONTEXT_CHARS = 200


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _section_prompt(audience: str, summary: str, previous_text: str, part: dict, style_policy: str) -> str:
    position = f"{part.get('name', '')}({part.get('function', '')})"
    previous_block = previous_text if previous_text else "(なし。これは最初のセクションです)"
    lines = [
        f"宛先: {audience}",
        f"これまでの要約: {summary or '(なし)'}",
        "直前セクション全文:",
        previous_block,
        f"構成上の現在位置: {position}",
        f"文体方針: {style_policy or '(指定なし)'}",
        "このセクションの本文を執筆してください。",
    ]
    return "\n".join(lines)


def _smoothing_prompt(tail: str, head: str) -> str:
    return (
        "次の接続部を平滑化してください。前半セクションの末尾と後半セクションの冒頭を"
        "自然につなげた新しい接続部のみを返してください。\n"
        f"---前半末尾---\n{tail}\n---後半冒頭---\n{head}\n"
    )


def write_draft(work, composition: dict, audience: str, author: Author, *, version: int = 1) -> Path:
    """composition["parts"] を階層文脈方式で順に執筆し、全体通読パスで縫合を平滑化する."""
    parts = composition.get("parts", [])
    style_policy = composition.get("style_policy", "")

    sections: list[str] = []
    accumulated = ""
    for part in parts:
        previous_text = sections[-1] if sections else ""
        summary = accumulated[:_SUMMARY_CHARS]
        prompt = _section_prompt(audience, summary, previous_text, part, style_policy)
        text = author(prompt)
        sections.append(text)
        accumulated += text

    # 全体通読パス: 隣接セクション間の縫い目を平滑化する。ただし前partの
    # intentional_break が True の縫い目はスキップ（意図的断絶の保存, PLAN §6.2）。
    for i in range(len(parts) - 1):
        if parts[i].get("intentional_break"):
            continue
        tail = sections[i][-_SEAM_CONTEXT_CHARS:]
        head = sections[i + 1][:_SEAM_CONTEXT_CHARS]
        smoothed = author(_smoothing_prompt(tail, head))
        sections[i] = sections[i][: len(sections[i]) - len(tail)] + smoothed
        sections[i + 1] = sections[i + 1][len(head):]

    draft_text = "\n\n".join(sections)
    path = work.draft_path(version)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(draft_text, encoding="utf-8")
    return path


def pipeline_to_draft(
    work,
    niche: dict,
    audience: str,
    author: Author,
    critic: Critic,
    *,
    generations: int = 2,
    poetics: str = "",
) -> Path:
    """ニッチ報告→criteria→3案→進化→drafts/v1.md を全自動でつなぐ（PLAN §10 M3）."""
    criteria_path = derive_criteria(work, niche, audience, author, poetics=poetics)
    criteria_text = criteria_path.read_text(encoding="utf-8")

    proposals = generate_proposals(work, criteria_text, [], audience, author, n=3)
    winner = evolve(work, proposals, criteria_text, audience, author, critic, generations=generations)

    work.append_decision(
        {
            "ts": _now_iso(),
            "layer": "L4",
            "decision": f"構成案を確定: {winner.get('form', '')}",
            "reason": "criteria.mdの基準で進化ループを実施し、最終世代でcriticスコア最大の案を採用した",
            "decided_by": "author_primary",
        }
    )

    path = write_draft(work, winner, audience, author)

    work.append_decision(
        {
            "ts": _now_iso(),
            "layer": "L5",
            "decision": f"原稿 v1 の執筆を完了: {path.name}",
            "reason": "階層文脈方式で各部分を執筆し、全体通読パスで意図的断絶以外の縫い目を平滑化した",
            "decided_by": "author_primary",
        }
    )

    return path
