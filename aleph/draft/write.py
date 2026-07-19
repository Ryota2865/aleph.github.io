"""L5 執筆（PLAN §6.2）— 部分執筆→結合→全体通読。階層文脈方式。意図的断絶は保存.

施工: M3。正典は `tests/test_m3_acceptance.py`。
部分執筆の各プロンプトには (a) 宛先 (b) これまでの要約 (c) 直前セクション全文
(d) 構成上の現在位置 (e) 文体方針 を必ず含める（PLAN §6.2）。
全体通読パスでは縫い目ごとに「平滑化」を依頼するが、intentional_break=True の
縫い目（前partが担う）はスキップし、意図的な断絶を保存する。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from aleph.compose.generate import derive_criteria, evolve, generate_proposals
from aleph.core.evaluation import EvaluationPacket
from aleph.core.work_snapshot import WorkReader

Author = Callable[[str], str]
Critic = Callable[[str], str]

_SUMMARY_CHARS = 400
_SEAM_CONTEXT_CHARS = 200
_FIRST_PERSON_MARKERS = ("私", "僕", "俺", "わたし", "ぼく", "おれ")
_THIRD_PERSON_POLICY_MARKERS = ("三人称", "第三人称")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _section_prompt(
    audience: str,
    summary: str,
    previous_text: str,
    part: dict,
    style_policy: str,
    evaluation_context: str = "",
) -> str:
    position = f"{part.get('name', '')}({part.get('function', '')})"
    previous_block = previous_text if previous_text else "(なし。これは最初のセクションです)"
    lines = [
        f"宛先: {audience}",
        f"これまでの要約: {summary or '(なし)'}",
        "直前セクション全文:",
        previous_block,
        f"構成上の現在位置: {position}",
        f"文体方針: {style_policy or '(指定なし)'}",
        *( [evaluation_context] if evaluation_context else [] ),
        "このセクションの本文を執筆してください。",
    ]
    return "\n".join(lines)


def _smoothing_prompt(tail: str, head: str) -> str:
    return (
        "次の接続部を平滑化してください。前半セクションの末尾と後半セクションの冒頭を"
        "自然につなげた新しい接続部のみを返してください。\n"
        f"---前半末尾---\n{tail}\n---後半冒頭---\n{head}\n"
    )


def _composition_expects_third_person(composition: dict) -> bool:
    policy = json.dumps(
        {
            "style_policy": composition.get("style_policy", ""),
            "point_of_view": composition.get("point_of_view", ""),
            "viewpoint": composition.get("viewpoint", ""),
            "parts": composition.get("parts", []),
        },
        ensure_ascii=False,
    )
    return any(marker in policy for marker in _THIRD_PERSON_POLICY_MARKERS)


def _uses_first_person(text: str) -> bool:
    return any(marker in text for marker in _FIRST_PERSON_MARKERS)


def _record_perspective_deviation(work, composition: dict, draft_text: str) -> None:
    if not _composition_expects_third_person(composition) or not _uses_first_person(draft_text):
        return
    work.append_decision(
        {
            "ts": _now_iso(),
            "layer": "L5",
            "decision": "構成逸脱: 三人称方針に対し本文に一人称語が出現",
            "reason": "winner の視点/style_policy と本文の人称が食い違ったため、作品は変更せず記録した",
            "decided_by": "write_draft",
        }
    )


def write_draft(
    work,
    composition: dict,
    audience: str,
    author: Author,
    *,
    version: int = 1,
    packet: EvaluationPacket | None = None,
) -> Path:
    """composition["parts"] を階層文脈方式で順に執筆し、全体通読パスで縫合を平滑化する."""
    parts = composition.get("parts", [])
    style_policy = composition.get("style_policy", "")

    sections: list[str] = []
    accumulated = ""
    for part in parts:
        previous_text = sections[-1] if sections else ""
        summary = accumulated[:_SUMMARY_CHARS]
        prompt = _section_prompt(
            audience,
            summary,
            previous_text,
            part,
            style_policy,
            packet.render_for("L5") if packet is not None else "",
        )
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
    _record_perspective_deviation(work, composition, draft_text)
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
    materials: list | None = None,
    criteria_constraints: str = "",
) -> Path:
    """ニッチ報告→criteria→3案→進化→drafts/v1.md を全自動でつなぐ（PLAN §10 M3）.

    COMPOSE 途中のクラッシュ再開でauthor呼び出し（実費）を繰り返さないよう、
    ディスク上の成果物（criteria.md / proposal_*.json / winner.json）が既に
    あればそれを再利用する。作品ディレクトリは作品ごとに独立なので安全。
    """
    from aleph.compose.generate import _PROPOSAL_REQUIRED_FIELDS

    criteria_path = work.compositions / "criteria.md"
    if not criteria_path.exists():
        extra = {"constraints": criteria_constraints} if criteria_constraints else {}
        criteria_path = derive_criteria(work, niche, audience, author, poetics=poetics, **extra)
    else:
        print("pipeline_to_draft: reusing criteria.md", file=sys.stderr)
    criteria_text = criteria_path.read_text(encoding="utf-8")
    packet = EvaluationPacket.for_planned_draft(
        WorkReader(work.dir).snapshot(), 1
    )
    packet.validate()
    l4_context = packet.render_for("L4")

    proposals = []
    for p in sorted(work.compositions.glob("proposal_*.json")):
        try:
            item = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and all(f in item for f in _PROPOSAL_REQUIRED_FIELDS):
            proposals.append(item)
    if len(proposals) >= 3:
        print(f"pipeline_to_draft: reusing {len(proposals)} proposals", file=sys.stderr)
    else:
        proposals = generate_proposals(work, l4_context, materials or [], audience, author, n=3)

    winner_path = work.compositions / "winner.json"
    if winner_path.exists():
        winner = json.loads(winner_path.read_text(encoding="utf-8"))
        print("pipeline_to_draft: reusing winner.json", file=sys.stderr)
    else:
        winner = evolve(work, proposals, l4_context, audience, author, critic, generations=generations)
        winner_path.write_text(json.dumps(winner, ensure_ascii=False, indent=2), encoding="utf-8")

    work.append_decision(
        {
            "ts": _now_iso(),
            "layer": "L4",
            "decision": f"構成案を確定: {winner.get('form', '')}",
            "reason": "criteria.mdの基準で進化ループを実施し、最終世代でcriticスコア最大の案を採用した",
            "decided_by": "author_primary",
        }
    )

    path = write_draft(work, winner, audience, author, packet=packet)

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
