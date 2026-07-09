"""L4 構成層（PLAN §6.1）— 基準の導出・最低3系統の構成案・交配/変異の進化ループ.

施工: M3。正典は `tests/test_m3_acceptance.py`。
最重要契約（PLAN §7.1 Goodhart回避）: 進化ループのauthor向けプロンプトに
criticの数値スコアや "score" の語を絶対に含めない。渡すのは自然言語の批評
（critique文字列）のみ。数値スコアは evolution.jsonl（擱筆判断用の記録）にだけ残す。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

Author = Callable[[str], str]
Critic = Callable[[str], str]

_PROPOSAL_REQUIRED_FIELDS = ("form", "parts", "material_placement", "style_policy", "length_estimate")
_MAX_PROPOSAL_ATTEMPTS = 3  # 初回 + 再要求2回（M3_spec.md）


# ---------------------------------------------------------------- JSON頑健パース
# aleph.explore.niche._extract_json_object と同じ方式（先頭からdictを走査して
# raw_decodeを試す）で、配列版を自作する。他ワーカー担当のexploreモジュールには
# 依存しない（編集許可ファイルの独立性を保つ）。

def _extract_json_object(text: str) -> dict | None:
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


def _extract_json_array(text: str) -> list | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "[":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, list):
            return value
    return None


# ---------------------------------------------------------------- 基準の導出（§6.1）

def derive_criteria(work, niche: dict, audience: str, author: Author, *, poetics: str = "") -> Path:
    """作品ごとに「この作品が満たすべき美的基準」をauthorに論述させ criteria.md へ保存する.

    プロンプトには宛先（PLAN §3）と詩学（PLAN §7.4、あれば）を必ず注入する。
    """
    lines = [
        "この作品が満たすべき美的基準は何か、論述してください。",
        f"ニッチ: {niche.get('description', '')}",
        f"宛先: {audience}",
    ]
    if poetics:
        lines.append(f"詩学: {poetics}")
    prompt = "\n".join(lines)

    response = author(prompt)
    text = response if "基準" in response else f"# 基準\n\n{response}"

    path = work.compositions / "criteria.md"
    work.compositions.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------- 構成案の生成（§6.1）

def _summarize_materials(materials: list) -> str:
    if not materials:
        return "(素材なし)"
    parts = []
    for item in materials:
        if isinstance(item, dict):
            parts.append(str(item.get("summary") or item.get("content") or item.get("id") or item))
        else:
            parts.append(str(item))
    return "; ".join(parts)


def _proposal_prompt(criteria: str, audience: str, materials_summary: str, n: int, retry: int) -> str:
    lines = [
        f"構成案を{n}系統、JSON配列で返してください。",
        "各案は次のフィールドを必ず持つこと: form, parts(各partはname/function/"
        "intentional_breakを持つ配列), material_placement, style_policy, length_estimate。",
        f"基準: {criteria}",
        f"宛先: {audience}",
        f"素材: {materials_summary}",
    ]
    if retry:
        lines.append(f"(再要求 {retry}回目。必須フィールドを漏らさないこと)")
    return "\n".join(lines)


def generate_proposals(
    work, criteria: str, materials: list, audience: str, author: Author, *, n: int = 3
) -> list[dict]:
    """構成案をn系統以上、必須フィールドつきで生成し保存する（PLAN §6.1）."""
    materials_summary = _summarize_materials(materials)
    valid: list[dict] = []
    for attempt in range(_MAX_PROPOSAL_ATTEMPTS):
        prompt = _proposal_prompt(criteria, audience, materials_summary, n, attempt)
        response = author(prompt)
        parsed = _extract_json_array(response) or []
        valid = [
            item
            for item in parsed
            if isinstance(item, dict) and all(field in item for field in _PROPOSAL_REQUIRED_FIELDS)
        ]
        if len(valid) >= n:
            break

    work.compositions.mkdir(parents=True, exist_ok=True)
    for index, proposal in enumerate(valid, start=1):
        path = work.compositions / f"proposal_{index}.json"
        path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")
    return valid


# ---------------------------------------------------------------- 進化ループ（§6.1・§7.1）

def _critic_prompt(candidate: dict, criteria: str) -> str:
    return (
        "次の構成案を基準に照らして採点してください。"
        'JSON {"score": 0-10の数値, "critique": "自然言語の批評"} で返してください。\n'
        f"基準: {criteria}\n"
        f"構成案: {json.dumps(candidate, ensure_ascii=False)}"
    )


def _crossover_prompt(candidate: dict, criteria: str, audience: str, critique: str) -> str:
    # Goodhart回避（PLAN §7.1）: このプロンプトには critic の数値・"score"の語を
    # 一切含めない。批評の自然言語（critique）のみを渡す。
    return (
        "以下の構成案について、批評をふまえて交配・変異させた新しい構成案を"
        "JSONオブジェクト1件で返してください。\n"
        f"基準: {criteria}\n"
        f"宛先: {audience}\n"
        f"元の構成案: {json.dumps(candidate, ensure_ascii=False)}\n"
        f"批評: {critique}\n"
    )


def evolve(
    work,
    proposals: list[dict],
    criteria: str,
    audience: str,
    author: Author,
    critic: Critic,
    *,
    generations: int = 2,
) -> dict:
    """構成案を基準で検討・交配・変異させる進化ループ（PLAN §6.1）を回す.

    各世代:
      1. critic に各案+criteriaを渡し {"score","critique"} を得る
      2. authorへの次プロンプトには critique 文字列のみを渡す（数値スコア禁止）
      3. 最良案の交配・変異をauthorに依頼し、次世代候補へ加える
      4. evolution.jsonl に世代記録を追記（scoreはここに記録してよい）
    最終世代で critic score が最大の案を返す。
    """
    candidates: list[dict] = list(proposals)
    winner: dict = candidates[0] if candidates else {}
    log_path = work.compositions / "evolution.jsonl"
    work.compositions.mkdir(parents=True, exist_ok=True)

    for generation in range(1, generations + 1):
        critiques = []
        scored = []
        for candidate in candidates:
            response = critic(_critic_prompt(candidate, criteria))
            parsed = _extract_json_object(response) or {}
            try:
                score = float(parsed.get("score", 0.0))
            except (TypeError, ValueError):
                score = 0.0
            critique_text = str(parsed.get("critique", ""))
            critiques.append({"form": candidate.get("form", ""), "score": score, "critique": critique_text})
            scored.append((score, critique_text, candidate))

        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best_critique, best_candidate = scored[0]
        winner = best_candidate

        crossover_prompt = _crossover_prompt(best_candidate, criteria, audience, best_critique)
        response = author(crossover_prompt)
        new_candidate = _extract_json_object(response)

        next_generation = list(candidates)
        if new_candidate:
            next_generation.append(new_candidate)

        record = {"generation": generation, "critiques": critiques, "n_candidates": len(candidates)}
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        candidates = next_generation

    return winner
