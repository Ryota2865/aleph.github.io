"""L7 複数LLM介在判断（PLAN §7.3c）— 批評は常に複数、執筆は単独が既定。行き詰まり検知で第二モデル

施工: M5。既定は単独執筆(声の統一)。自己類似度の高止まり・意図的多声性・author要請のいずれかで第二モデルを検討する。
"""
from __future__ import annotations


def second_author_needed(
    *,
    self_similarity: float,
    polyphony_intended: bool,
    author_requested: bool,
    threshold: float = 0.9,
) -> dict:
    """執筆へ第二モデルを入れるべきかを判定する（PLAN §7.3c）.

    既定はFalse(執筆は単独=声の統一)。以下いずれかでTrue:
    - 自己類似度が threshold を超える(文体的行き詰まり)
    - 構成に意図的な多声性が含まれる
    - authorが自ら要請した
    """
    reasons = []
    if self_similarity > threshold:
        reasons.append(
            f"版間の自己類似度{self_similarity:.2f}がしきい値{threshold}を超え、文体的行き詰まりの兆候がある"
        )
    if polyphony_intended:
        reasons.append("構成に意図的な多声性が含まれる")
    if author_requested:
        reasons.append("authorが自ら第二モデルを要請した")

    needed = bool(reasons)
    reason = (
        "; ".join(reasons)
        if reasons
        else "行き詰まり・意図的多声性・author要請のいずれも該当しないため、単独執筆(声の統一)を維持する"
    )
    return {"needed": needed, "reason": reason}
