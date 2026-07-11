"""L7 擱筆判断（PLAN §7.3a）— 収束/完成宣言/過剰彫琢警報の3経路。予算切れで強制起動

施工: M5。優先順位は budget → over_polish（警報つき） → convergence。
スコアは執筆プロンプトへ渡さず擱筆判断専用の情報として扱う（Goodhart回避。PLAN §16.4）。
"""
from __future__ import annotations

import json
from typing import Callable


def _extract_json_object(text: str) -> dict | None:
    """応答文字列中の最初のJSONオブジェクトを頑健に取り出す（aleph/explore/niche.py と同方式）."""
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


def decide_stop(
    *,
    trajectory: list[dict],
    instructions_history: list[list[str]],
    k: int = 3,
    epsilon: float = 0.05,
    budget_exhausted: bool = False,
) -> dict:
    """擱筆の3経路を優先順位つきで判定する（PLAN §7.3a）.

    優先順:
    (1) budget_exhausted → 強制擱筆
    (2) 過剰彫琢: 直近k版でmean_scoreが単調上昇かつnovelty_distが単調減少（無難化）
        → 警報つき即時擱筆推奨
    (3) 収束: 直近k版のスコア改善幅がすべてepsilon未満、かつ改稿指示が循環（同一指示の再出現）
    いずれでもなければ継続。
    """
    if budget_exhausted:
        return {
            "stop": True,
            "path": "budget",
            "reason": "予算・時間の残量が尽きたため強制的に擱筆する。",
        }

    recent = trajectory[-k:] if trajectory else []

    if len(recent) >= 2 and all("novelty_dist" in record for record in recent):
        scores = [float(record["mean_score"]) for record in recent]
        novelties = [float(record["novelty_dist"]) for record in recent]
        score_rising = all(b > a for a, b in zip(scores, scores[1:]))
        novelty_falling = all(b < a for a, b in zip(novelties, novelties[1:]))
        if score_rising and novelty_falling:
            return {
                "stop": True,
                "path": "over_polish",
                "alarm": True,
                "reason": (
                    "直近版でスコアは上昇し続けているが新奇性査読の距離が縮んでいる"
                    "(無難化)。過剰彫琢として即時擱筆を推奨する(PLAN §16.4)。"
                ),
            }

    if len(recent) >= 2:
        scores = [float(record["mean_score"]) for record in recent]

        # 退行: 直近の改稿でスコアが epsilon 超下落 = 改稿が作品を損ねている。
        # 磨き続けても回復する保証はなく実費だけが増える(w0002実ラン 8.80→8.33 で観測。
        # 擱筆判断の趣旨=「これ以上の介入が作品を良くしない徴候で止まる」PLAN §7.3a に従う)
        if scores[-1] < scores[-2] - epsilon:
            return {
                "stop": True,
                "path": "regression",
                "reason": (
                    f"直近の改稿でスコアが {scores[-2]:.2f}→{scores[-1]:.2f} と下落した。"
                    "改稿が作品を損ねているため擱筆する。"
                ),
            }

        improvements = [b - a for a, b in zip(scores, scores[1:])]
        converged_score = all(delta < epsilon for delta in improvements)

        recent_instructions = instructions_history[-k:] if instructions_history else []
        flattened = [text for group in recent_instructions for text in group]
        cycled = len(flattened) != len(set(flattened))

        if converged_score and cycled:
            return {
                "stop": True,
                "path": "convergence",
                "reason": (
                    f"直近{len(recent)}版のスコア改善幅がすべてepsilon={epsilon}未満で、"
                    "かつ改稿指示に同一指摘の再出現(循環)が確認された。"
                ),
            }

    return {
        "stop": False,
        "path": None,
        "reason": "改善余地があるか、循環・過剰彫琢いずれの兆候も確認できない。",
    }


def completion_declaration(
    draft_text: str,
    author: Callable[[str], str],
    adversary: Callable[[str], str],
) -> dict:
    """authorの完成宣言をadversaryが反駁できなければ完成とする（PLAN §7.3a）."""
    author_prompt = (
        "以下の草稿について、なぜこれで完成と言えるかを論述してください。"
        "彫琢を続けることの効用が尽きた根拠を含めること。\n\n"
        f"草稿:\n{draft_text}"
    )
    declaration = author(author_prompt)

    adversary_prompt = (
        "次の完成宣言に対し、反駁できる未回収の論点があれば反駁してください。"
        '反駁できなければ rebutted を false としてください。'
        'JSON {"rebutted": true|false, "rationale": "..."} のみで返答してください。\n\n'
        f"完成宣言:\n{declaration}"
    )
    response = adversary(adversary_prompt)
    parsed = _extract_json_object(response) or {}
    rebutted = bool(parsed.get("rebutted", False))
    rationale = str(parsed.get("rationale", ""))

    return {
        "completed": not rebutted,
        "declaration": declaration,
        "rebuttal": rationale,
    }
