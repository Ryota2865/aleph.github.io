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
from aleph.critique.style import rationing_instructions
from aleph.explore.niche import _extract_json_object
from aleph.materia.ai_native import perplexity_curve


_SCORE_PATTERNS = (
    re.compile(r"\bscore\b|スコア", re.IGNORECASE),
    re.compile(r"\d+(?:\.\d+)?\s*(?:点|/10|/100)"),
    re.compile(r"\d+\.\d+"),
)

# 査読に渡す草稿の上限(字)。ローカル審級の文脈長(20480トークン、うち生成4096)に
# プロンプト外装込みで収まる値(日本語は1字≈0.8-1トークン)。超過分は冒頭・中間・末尾の
# 有界セグメントで査読し、クライマックスを必ず審級へ載せる。
_REVIEW_EXCERPT_CHARS = 18000
_REVIEW_SEGMENT_CHARS = 6000


def sanitize_critique(text: str) -> str:
    """author プロンプトへ渡す批評文から数値スコアらしき断片だけを除去する."""
    sanitized = text
    for pattern in _SCORE_PATTERNS:
        sanitized = pattern.sub("[数値除去]", sanitized)
    return sanitized


def _review_segments(draft_text: str) -> tuple[list[tuple[str, str]], int]:
    """長い草稿を冒頭・中間・末尾の査読セグメントへ縮約する."""
    full_len = len(draft_text)
    if full_len <= _REVIEW_EXCERPT_CHARS:
        return [("全文", draft_text)], full_len

    seg = _REVIEW_SEGMENT_CHARS
    mid = full_len // 2
    middle_start = max(0, mid - seg // 2)
    middle_end = min(full_len, middle_start + seg)
    return [
        ("冒頭", draft_text[:seg]),
        ("中間", draft_text[middle_start:middle_end]),
        ("末尾（クライマックス）", draft_text[-seg:]),
    ], full_len


def _review_input(draft_text: str) -> str:
    """審級に渡す有界な草稿テキスト。長文では全文長と区切り注記を明記する."""
    segments, full_len = _review_segments(draft_text)
    if len(segments) == 1:
        return draft_text
    blocks = [
        f"【査読セグメント: {label} / 全文{full_len}字】\n{text}"
        for label, text in segments
    ]
    blocks.append(f"【注記】全文{full_len}字から冒頭・中間・末尾を各約{_REVIEW_SEGMENT_CHARS}字で抜粋。")
    return "\n\n".join(blocks)


def _llm_is_primary_audience(audience: str) -> bool:
    """宛先配合で「LLM」が最大係数かを判定する（§5.4技法の適用条件）."""
    weights: dict[str, float] = {}
    for label, value in re.findall(r"([^/\n,、]+?)\s*[=:：]?\s*([0-9]+(?:\.[0-9]+)?)", audience or ""):
        try:
            weights[label.strip()] = float(value)
        except ValueError:
            continue
    if not weights:
        return False
    llm_weights = [v for k, v in weights.items() if "LLM" in k]
    if not llm_weights:
        return False
    others = [v for k, v in weights.items() if "LLM" not in k]
    return not others or max(llm_weights) >= max(others)


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

    # 埋め込みモデルの文脈長(8192トークン)を超える草稿は埋め込みが 500 になる(w0003実ラン)。
    # 冒頭・中間・末尾の有界セグメントを埋め込み平均して全体の表現とする。
    seg = 5000
    if len(draft_text) > seg:
        mid = len(draft_text) // 2
        segments = [draft_text[:seg], draft_text[mid - seg // 2: mid + seg // 2], draft_text[-seg:]]
    else:
        segments = [draft_text]
    vectors = np.asarray(embedder(segments), dtype=np.float32)
    query = vectors.mean(axis=0)
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


def _instruction_lines(text: str) -> list[str]:
    normalized = text.strip()
    if not normalized or normalized in {"[]", "なし", "特になし"} or "ありません" in normalized:
        return []
    parsed = _extract_json_object(normalized)
    if isinstance(parsed, dict):
        items: list[str] = []
        for key in ("issues", "items", "instructions", "points"):
            value = parsed.get(key)
            if isinstance(value, list):
                items.extend(str(item) for item in value)
            elif isinstance(value, str):
                items.append(value)
        if not items:
            return []
        normalized = "\n".join(items)
    lines: list[str] = []
    for raw in normalized.splitlines():
        line = re.sub(r"^\s*(?:[-*・]|\d+[\).、])\s*", "", raw).strip()
        if not line or line in {"[]", "なし", "特になし"} or "ありません" in line:
            continue
        lines.append(line)
    return lines


def _distill_criteria_issues(criteria_review: dict, scout: Callable[[str], str] | None) -> list[str]:
    critiques = [
        sanitize_critique(str(critique)).strip()
        for critique in criteria_review.get("critiques", [])
        if str(critique).strip()
    ]
    if not critiques or scout is None:
        return []
    prompt = (
        "次の批評から「直すべき点」だけを箇条書きで、優先順位順に抽出してください。"
        "褒め言葉は除いてください。直すべき点がなければ空で返してください。\n"
        f"批評:\n" + "\n".join(f"- {critique}" for critique in critiques)
    )
    response = sanitize_critique(scout(prompt))
    return _instruction_lines(response)


def _synthesize_revise_instructions(
    criteria_review: dict,
    technical: dict,
    scout: Callable[[str], str] | None = None,
    *,
    draft_text: str = "",
) -> list[str]:
    """陪審批評+技術指摘から、数値を含まない自然言語の改稿指示を合成する（Goodhart回避）."""
    instructions: list[str] = []
    for issue in _distill_criteria_issues(criteria_review, scout):
        instructions.append(sanitize_critique(f"陪審の直すべき点に応える: {issue}"))
    for issue in technical.get("issues", []):
        if isinstance(issue, dict):
            note = str(issue.get("note") or issue.get("where") or issue.get("type") or "").strip()
        else:
            note = str(issue).strip()
        if note:
            instructions.append(sanitize_critique(f"技術指摘に応える: {note}"))
    instructions.extend(sanitize_critique(i) for i in rationing_instructions(draft_text))
    return instructions


def _perplexity_review(draft_text: str, reader_llm) -> dict:
    segments, full_len = _review_segments(draft_text)
    prompts = [
        f"LLM読者として次の査読セグメントを読んでください。全文{full_len}字中の{label}です。\n{text}"
        for label, text in segments
    ]
    curve = perplexity_curve(prompts, reader_llm)
    return {
        "unit": "mean_logprob_per_segment",
        "segments": [
            {"label": label, "mean_logprob": value}
            for (label, _text), value in zip(segments, curve)
        ],
        "curve": curve,
    }


def _write_report_markdown(work, version: int, report: dict) -> None:
    cr = report["criteria_review"]
    perplexity_lines: list[str] = []
    if "perplexity" in report:
        perplexity = report["perplexity"]
        perplexity_lines = [
            "## LLM審級: perplexity曲線",
            f"- 単位: {perplexity.get('unit')}",
            *(
                f"- {segment.get('label')}: {segment.get('mean_logprob')}"
                for segment in perplexity.get("segments", [])
            ),
            "",
        ]
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
        *perplexity_lines,
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
    reader_llm=None,
) -> dict:
    """5審級（技術/基準/新奇性/読者/敵対的）を実行し、reviews/v{version}.md に報告を書く（PLAN §7.1）."""
    # 過大な草稿は有界セグメントで査読する。ローカル審級の文脈長(20480)を超えると
    # llama-server が 400 を返して査読不能になる(w0003 実ラン: 21万字の草稿)。
    # 草稿長のガバナンス(length_estimate の強制)は別途の改善債務。
    review_text = _review_input(draft_text)
    technical = _technical_review(scout, review_text)
    criteria_review = _criteria_review(jury, criteria, review_text)
    novelty = novelty_review(review_text, embedder, index_dir)
    reader_result = _reader_review(reader, review_text, audience)
    adversary = adversary_review(review_text, criteria, search_fn, scout)
    revise_instructions = _synthesize_revise_instructions(
        criteria_review,
        technical,
        scout,
        draft_text=draft_text,
    )

    report = {
        "technical": technical,
        "criteria_review": criteria_review,
        "novelty": novelty,
        "reader": reader_result,
        "adversary": adversary,
        "revise_instructions": revise_instructions,
    }
    if reader_llm is not None and _llm_is_primary_audience(audience):
        report["perplexity"] = _perplexity_review(draft_text, reader_llm)
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
    reader_llm=None,
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
            reader_llm=reader_llm,
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

    rows: list[dict] = []
    if traj_path.exists():
        for line in traj_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    if rows:
        best_row = max(rows, key=lambda row: float(row.get("mean_score", 0.0)))
        best_version = int(best_row.get("version", version))
        work.append_decision(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "layer": "L6",
                "decision": f"採用 v{best_version}",
                "reason": f"trajectory.jsonl の mean_score 最大版を best_version として記録",
                "decided_by": "critique_revise_loop",
                "best_version": best_version,
            }
        )

    return version
