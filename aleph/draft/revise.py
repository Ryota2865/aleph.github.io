"""L5 改稿（PLAN §7.2）— 自然言語の批評のみを入力とする。スコアは渡されない(Goodhart回避, §7.1)

施工: M4.

最重要契約（テストが機械検査する）: authorへのプロンプトに数値スコアや"score"の語を
決して混ぜない。report辞書をそのままstr()/json.dumpsで埋め込むと数値が混入するため、
必要な文字列フィールド(criteria_review.critiques / revise_instructions)だけを取り出して
組み立てること。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Callable

from aleph.critique.review import sanitize_critique
from aleph.core.evaluation import EvaluationPacket


def _split_heading_sections(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    sections: list[list[str]] = []
    current: list[str] = []
    has_heading = False
    for line in lines:
        if line.startswith("## "):
            has_heading = True
            if current:
                sections.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append(current)
    if not has_heading:
        return []
    return ["".join(section) for section in sections]


def _keyword_fragments(text: str) -> set[str]:
    fragments = set(re.findall(r"[一-龯々〆ヵヶ]{2,}|[ァ-ンー]{2,}|[A-Za-z][A-Za-z0-9_]{1,}", text))
    return {fragment for fragment in fragments if len(fragment) >= 2}


def _brief(text: str, limit: int = 300) -> str:
    return " ".join(text.strip().split())[:limit]


def _section_revise_prompt(
    *,
    audience: str,
    section: str,
    previous_section: str,
    next_section: str,
    instructions: list[str],
) -> str:
    lines = [
        f"宛先: {audience}",
        "",
        "以下の対象節だけを、該当する批評と改稿指示に基づいて改稿してください。",
        "前後の要約は文脈のためだけに使い、出力は改稿後の対象節だけにしてください。",
        "見出しがある場合は見出しを保持してください。",
        "",
        "## 前の節の要約",
        _brief(previous_section) or "(なし)",
        "",
        "## 対象節",
        section,
        "",
        "## 次の節の要約",
        _brief(next_section) or "(なし)",
        "",
        "## 該当する批評と改稿指示",
        *(f"- {instruction}" for instruction in instructions),
    ]
    return "\n".join(lines)


def _targeted_section_revise(
    previous_text: str,
    *,
    audience: str,
    author: Callable[[str], str],
    instructions: list[str],
) -> str:
    sections = _split_heading_sections(previous_text)
    if not sections:
        return previous_text
    revised_sections: list[str] = []
    for index, section in enumerate(sections):
        section_instructions = [
            instruction
            for instruction in instructions
            if any(fragment in section for fragment in _keyword_fragments(instruction))
        ]
        if not section_instructions:
            revised_sections.append(section)
            continue
        prompt = _section_revise_prompt(
            audience=audience,
            section=section,
            previous_section=sections[index - 1] if index > 0 else "",
            next_section=sections[index + 1] if index + 1 < len(sections) else "",
            instructions=section_instructions,
        )
        revised_sections.append(author(prompt))
    return "".join(revised_sections)


def revise(
    work,
    report: dict,
    audience: str,
    author: Callable[[str], str],
    *,
    version: int,
    packet: EvaluationPacket | None = None,
) -> Path:
    """前版全文+批評+改稿指示(自然言語のみ)を author に渡し、次版を書く（PLAN §7.2）."""
    previous_text = work.draft_path(version).read_text(encoding="utf-8")
    criteria_review = report.get("criteria_review", {})
    critiques = [sanitize_critique(str(c)) for c in criteria_review.get("critiques", [])]
    revise_instructions = [sanitize_critique(str(i)) for i in report.get("revise_instructions", [])]

    lines = [
        f"宛先: {audience}",
        "",
        "以下は前版の草稿です。批評と改稿指示だけに基づいて改稿してください"
        "（数値の評点は与えられません。文章そのものの質で判断してください）。",
        *( [packet.render_for("L5")] if packet is not None else [] ),
        "",
        "## 前版",
        previous_text,
        "",
        "## 批評",
        *(f"- {critique}" for critique in critiques),
        "",
        "## 改稿指示",
        *(f"- {instruction}" for instruction in revise_instructions),
    ]
    prompt = "\n".join(lines)

    revised_text = author(prompt)
    if len(revised_text) < len(previous_text) * 0.8:
        revised_text = _targeted_section_revise(
            previous_text,
            audience=audience,
            author=author,
            instructions=critiques + revise_instructions,
        )
        if len(revised_text) < len(previous_text) * 0.8:
            print("warning: revised text appears truncated; preserving previous draft", file=sys.stderr)
            revised_text = previous_text

    new_path = work.draft_path(version + 1)
    new_path.parent.mkdir(parents=True, exist_ok=True)
    new_path.write_text(revised_text, encoding="utf-8")
    return new_path
