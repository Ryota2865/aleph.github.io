"""L6 査読（PLAN §7.1）— 5審級を分離: 技術/基準/新奇性/読者/敵対的。合意スコアと不一致度を必ず併記

施工: M4.

最重要契約（PLAN §7.1 Goodhart回避）: 数値スコアは擱筆判断専用であり、author（draft/revise.py）
への改稿プロンプトへ決して混入しない。ここでは report を返すだけで、report を author へ渡す責務は
draft/revise.py 側にあり、そちらが自然言語の批評文字列だけを取り出す。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from aleph.critique.adversary import adversary_review
from aleph.critique.reader_model import reader_prompt
from aleph.explore.niche import _extract_json_object


_SCORE_PATTERNS = (
    re.compile(r"\bscore\b|スコア", re.IGNORECASE),
    re.compile(r"\d+(?:\.\d+)?\s*(?:点|/10|/100)"),
    re.compile(r"\d+\.\d+"),
)


def sanitize_critique(text: str) -> str:
    """author プロンプトへ渡す批評文から数値スコアらしき断片だけを除去する."""
    sanitized = text
    for pattern in _SCORE_PATTERNS:
        sanitized = pattern.sub("[数値除去]", sanitized)
    return sanitized


def _technical_review(scout: Callable[[str], str], draft_text: str) -> dict:
    """技術審級: 破綻・矛盾・冗長を scout に指摘させる（PLAN §7.1）."""
    prompt = (
        "草稿の技術的な破綻・矛盾・冗長を指摘してください。問題がなければ空リストで構いません。"
        'JSON {"issues": [{"type": "...", "where": "...", "note": "..."}, ...]} で返してください。\n'
        f"草稿:\n{draft_text}"
    )
    response = scout(prompt)
    parsed = _extract_json_object(response) or {}
    issues = parsed.get("issues", [])
    if not isinstance(issues, list):
        issues = []
    return {"issues": issues}


def _criteria_review(jury: list[Callable[[str], str]], criteria: str, draft_text: str) -> dict:
    """基準審級: 陪審の各員が独立に採点+論評する。合意(平均)と不一致度(母標準偏差)を必ず併記する."""
    scores: list[float] = []
    critiques: list[str] = []
    for juror in jury:
        prompt = (
            "以下の基準に照らして草稿を採点し、論評してください。"
            'JSON {"score": 0から10の数値, "critique": "..."} で返してください。\n'
            f"基準:\n{criteria}\n\n草稿:\n{draft_text}"
        )
        response = juror(prompt)
        parsed = _extract_json_object(response) or {}
        try:
            score = float(parsed.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        critique = str(parsed.get("critique", response))
        scores.append(score)
        critiques.append(critique)
    mean_score = float(np.mean(scores)) if scores else 0.0
    disagreement = float(np.std(scores)) if scores else 0.0  # 母標準偏差(ddof=0)
    return {"mean_score": mean_score, "disagreement": disagreement, "critiques": critiques}


def novelty_review(draft_text: str, embedder: Callable[[list[str]], np.ndarray], index_dir: str | Path) -> dict:
    """新奇性審級: 完成稿を埋め込み、M1プレーン索引(embeddings.npy/chunks.jsonl)への
    最近傍コサイン距離(1 - 最大コサイン類似度)を測る（PLAN §7.1-3）."""
    index_dir = Path(index_dir)
    embeddings = np.asarray(np.load(index_dir / "embeddings.npy"), dtype=np.float32)
    chunks: list[dict] = []
    with open(index_dir / "chunks.jsonl", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                chunks.append(json.loads(line))

    query = np.asarray(embedder([draft_text]), dtype=np.float32)[0]
    query_norm = float(np.linalg.norm(query))

    best_sim = -1.0
    best_idx = 0
    for idx in range(embeddings.shape[0]):
        vector = embeddings[idx]
        denom = query_norm * float(np.linalg.norm(vector))
        sim = float(np.dot(query, vector) / denom) if denom else 0.0
        if sim > best_sim:
            best_sim = sim
            best_idx = idx

    nearest_chunk_id = chunks[best_idx]["chunk_id"] if chunks else ""
    return {"nearest_dist": 1.0 - best_sim, "nearest_chunk_id": nearest_chunk_id}


def _reader_review(reader: Callable[[str], str], draft_text: str, audience: str) -> dict:
    """読者審級: reader_prompt で組み立てたプロンプトを reader に渡す."""
    prompt = reader_prompt(draft_text, audience)
    response = reader(prompt)
    parsed = _extract_json_object(response)
    if parsed is None:
        return {"raw": response}
    return parsed


def _synthesize_revise_instructions(criteria_review: dict, technical: dict) -> list[str]:
    """陪審批評+技術指摘から、数値を含まない自然言語の改稿指示を合成する（Goodhart回避）."""
    instructions: list[str] = []
    for critique in criteria_review.get("critiques", []):
        instructions.append(f"陪審の批評に応える: {critique}")
    for issue in technical.get("issues", []):
        if isinstance(issue, dict):
            note = str(issue.get("note") or issue.get("where") or issue.get("type") or "").strip()
        else:
            note = str(issue).strip()
        if note:
            instructions.append(f"技術指摘に応える: {note}")
    return instructions


def _write_report_markdown(work, version: int, report: dict) -> None:
    cr = report["criteria_review"]
    lines = [
        f"# 査読報告 v{version}",
        "",
        "## 技術審級",
        *(f"- {issue}" for issue in report["technical"].get("issues", [])),
        "",
        "## 基準審級",
        f"- 合意スコア(平均): {cr['mean_score']:.2f}",
        f"- 不一致度(母標準偏差): {cr['disagreement']:.2f}",
        *(f"- 批評: {c}" for c in cr.get("critiques", [])),
        "",
        "## 新奇性審級",
        f"- 最近傍距離: {report['novelty'].get('nearest_dist')}",
        f"- 最近傍チャンク: {report['novelty'].get('nearest_chunk_id')}",
        "",
        "## 読者審級",
        f"- {report['reader']}",
        "",
        "## 敵対的審級",
        f"- 既視的か: {report['adversary'].get('derivative')}",
        *(f"- 根拠: {ev}" for ev in report["adversary"].get("evidence", [])),
        "",
        "## 改稿指示",
        *(f"- {i}" for i in report.get("revise_instructions", [])),
        "",
    ]
    path = work.review_path(version)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_review(
    work,
    draft_text: str,
    criteria: str,
    audience: str,
    *,
    version: int,
    scout: Callable[[str], str],
    jury: list[Callable[[str], str]],
    reader: Callable[[str], str],
    embedder: Callable[[list[str]], np.ndarray],
    index_dir: str | Path,
    search_fn: Callable[..., list[dict]],
) -> dict:
    """5審級（技術/基準/新奇性/読者/敵対的）を実行し、reviews/v{version}.md に報告を書く（PLAN §7.1）."""
    technical = _technical_review(scout, draft_text)
    criteria_review = _criteria_review(jury, criteria, draft_text)
    novelty = novelty_review(draft_text, embedder, index_dir)
    reader_result = _reader_review(reader, draft_text, audience)
    adversary = adversary_review(draft_text, criteria, search_fn, scout)
    revise_instructions = _synthesize_revise_instructions(criteria_review, technical)

    report = {
        "technical": technical,
        "criteria_review": criteria_review,
        "novelty": novelty,
        "reader": reader_result,
        "adversary": adversary,
        "revise_instructions": revise_instructions,
    }
    _write_report_markdown(work, version, report)
    return report


def critique_revise_loop(
    work,
    criteria: str,
    audience: str,
    author: Callable[[str], str],
    *,
    scout: Callable[[str], str],
    jury: list[Callable[[str], str]],
    reader: Callable[[str], str],
    embedder: Callable[[list[str]], np.ndarray],
    index_dir: str | Path,
    search_fn: Callable[..., list[dict]],
    max_iters: int = 2,
) -> int:
    """v=1から REVISEループを max_iters 回まわす（PLAN §7.2・§10 M4）.

    各反復: run_review → reviews/trajectory.jsonl に版とスコア・不一致度を追記 →
    決定記録(layer L6) → revise で次版を生成。ジュリーローテーション(§7.1)はM5/M6配線。
    """
    from aleph.draft.revise import revise

    version = 1
    traj_path = work.dir / "reviews" / "trajectory.jsonl"
    traj_path.parent.mkdir(parents=True, exist_ok=True)

    for _ in range(max_iters):
        draft_text = work.draft_path(version).read_text(encoding="utf-8")
        report = run_review(
            work,
            draft_text,
            criteria,
            audience,
            version=version,
            scout=scout,
            jury=jury,
            reader=reader,
            embedder=embedder,
            index_dir=index_dir,
            search_fn=search_fn,
        )
        cr = report["criteria_review"]
        record = {
            "version": version,
            "mean_score": cr["mean_score"],
            "disagreement": cr["disagreement"],
            "novelty_dist": report.get("novelty", {}).get("nearest_dist"),
            "instructions": report.get("revise_instructions", []),
        }
        with open(traj_path, "a", encoding="utf-8") as target:
            target.write(json.dumps(record, ensure_ascii=False) + "\n")

        work.append_decision(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "layer": "L6",
                "decision": "review_complete",
                "reason": (
                    f"v{version} 査読完了: mean_score={cr['mean_score']:.2f}, "
                    f"disagreement={cr['disagreement']:.2f}"
                ),
                "decided_by": "critique_revise_loop",
            }
        )

        new_path = revise(work, report, audience, author, version=version)
        version = int(new_path.stem[1:])

    return version
