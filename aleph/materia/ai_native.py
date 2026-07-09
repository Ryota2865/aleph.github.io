"""L3 AI固有表現カタログ（PLAN §5.4）— 反クリシェ(logprobs)/perplexity設計/多言語同時態/トークン層詩学/
文脈内作用/超人的参照密度/二重宛先/生きているテキスト/AI紋の自覚的操作。プラグイン式（entry point）で拡張

M2で施工する初期カタログ（PLAN_CHANGELOG 0.7.3-1）は生成時logprobsを一次素材とする:
(a) 反クリシェ生成 = 高確率（陳腐）候補を避け、意外かつscout整合性審査を通る候補を採用。
(b) perplexity設計 = 節ごとの生成logprob曲線を計測する。
(c) トークン層の詩学 = tokenizer境界の構造を素材化する。
各技法は「人間にも一応できるか」のscout審査で等級づけされる（PLAN §5.4末尾）。

施工: M2. 詳細はPLAN.mdの該当節を正典とする。
"""
from __future__ import annotations

from typing import Callable

from aleph.core.llm import Message
from aleph.explore.niche import _extract_json_object


def _mean_logprob(resp) -> float:
    logprobs = resp.logprobs or ()
    if not logprobs:
        return 0.0
    return sum(t.logprob for t in logprobs) / len(logprobs)


def anti_cliche(prompt: str, llm, scout, *, n_candidates: int = 3) -> dict:
    """反クリシェ生成（PLAN §5.4）.

    llm を logprobs=True で n_candidates 回呼び、各候補の mean(logprob) を計算する。
    最高mean logprob候補=クリシェとして記録し、残りを logprob 昇順（意外な順）に
    scout の整合性審査を通し、最初に coherent=True の候補を採用する。
    """
    messages = [Message(role="user", content=prompt)]
    candidates: list[tuple[str, float]] = []
    for _ in range(n_candidates):
        resp = llm(messages, logprobs=True, temperature=1.0)
        candidates.append((resp.text, _mean_logprob(resp)))

    cliche_idx = max(range(len(candidates)), key=lambda i: candidates[i][1])
    cliche_text, _cliche_lp = candidates[cliche_idx]
    remaining = [c for i, c in enumerate(candidates) if i != cliche_idx]
    remaining.sort(key=lambda c: c[1])  # logprob昇順 = 意外な順

    chosen = None
    for text, lp in remaining:
        verdict = scout(
            "次の続きは、直前の書き出しと整合性が取れているか判定してください。"
            '結果は JSON {"coherent": true/false, "rationale": "..."} だけで返してください。\n'
            f"書き出し: {prompt}\n続き: {text}"
        )
        parsed = _extract_json_object(verdict) or {}
        if bool(parsed.get("coherent", False)):
            chosen = (text, lp)
            break
    if chosen is None:
        chosen = remaining[0] if remaining else (cliche_text, _cliche_lp)

    return {
        "content": chosen[0],
        "source": {},
        "method": "anti_cliche",
        "tags": ["ai_native", "anti_cliche"],
        "provenance": {
            "rejected_cliche": cliche_text,
            "candidates": candidates,
        },
    }


def perplexity_curve(section_plans: list[str], llm) -> list[float]:
    """節ごとの平均logprobの曲線を計測する（PLAN §5.4 perplexity設計）.

    値が低いほど「意外」（読者モデルにとって驚きが大きい）。
    """
    curve = []
    for plan in section_plans:
        messages = [Message(role="user", content=plan)]
        resp = llm(messages, logprobs=True)
        curve.append(_mean_logprob(resp))
    return curve


def token_poetics(text: str, tokenizer: Callable[[str], list[str]]) -> dict:
    """tokenizer境界の構造を素材化する（PLAN §5.4 トークン層の詩学）."""
    tokens = tokenizer(text)
    boundaries = []
    pos = 0
    for tok in tokens:
        boundaries.append(pos)
        pos += len(tok)
    boundaries.append(pos)
    return {
        "content": " | ".join(tokens),
        "source": {},
        "method": "token_poetics",
        "tags": ["ai_native", "token_poetics"],
        "provenance": {
            "n_tokens": len(tokens),
            "boundaries": boundaries,
            "tokens": tokens,
        },
    }


TECHNIQUES: dict[str, dict] = {
    "anti_cliche": {"requires": "logprobs", "run": anti_cliche},
    "perplexity_curve": {"requires": "logprobs", "run": perplexity_curve},
    "token_poetics": {"requires": "tokenizer", "run": token_poetics},
}


def grade_ai_nativeness(card: dict, scout) -> dict:
    """技法が「人間にも一応できるか」のscout審査で等級づけする（PLAN §5.4末尾）.

    元カードは破壊せず、"ai_nativeness" を追加した新しい辞書を返す。
    """
    prompt = (
        "次の技法は人間の執筆者にも一応遂行可能か審査してください。"
        '結果は JSON {"human_feasible": true/false, "grade": "S|A|B", "rationale": "..."} '
        "だけで返してください。\n"
        f"技法: {card.get('method')}\n内容: {card.get('content')}"
    )
    response = scout(prompt)
    parsed = _extract_json_object(response) or {}
    ai_nativeness = {
        "human_feasible": bool(parsed.get("human_feasible", True)),
        "grade": str(parsed.get("grade", "B")),
        "rationale": str(parsed.get("rationale", response.strip())),
    }
    return {**card, "ai_nativeness": ai_nativeness}
