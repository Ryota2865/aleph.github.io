"""L5 改稿（PLAN §7.2）— 自然言語の批評のみを入力とする。スコアは渡されない(Goodhart回避, §7.1)

施工: M4.

最重要契約（テストが機械検査する）: authorへのプロンプトに数値スコアや"score"の語を
決して混ぜない。report辞書をそのままstr()/json.dumpsで埋め込むと数値が混入するため、
必要な文字列フィールド(criteria_review.critiques / revise_instructions)だけを取り出して
組み立てること。
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable


def revise(work, report: dict, audience: str, author: Callable[[str], str], *, version: int) -> Path:
    """前版全文+批評+改稿指示(自然言語のみ)を author に渡し、次版を書く（PLAN §7.2）."""
    previous_text = work.draft_path(version).read_text(encoding="utf-8")
    criteria_review = report.get("criteria_review", {})
    critiques = [str(c) for c in criteria_review.get("critiques", [])]
    revise_instructions = [str(i) for i in report.get("revise_instructions", [])]

    lines = [
        f"宛先: {audience}",
        "",
        "以下は前版の草稿です。批評と改稿指示だけに基づいて改稿してください"
        "（数値の評点は与えられません。文章そのものの質で判断してください）。",
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

    new_path = work.draft_path(version + 1)
    new_path.parent.mkdir(parents=True, exist_ok=True)
    new_path.write_text(revised_text, encoding="utf-8")
    return new_path
