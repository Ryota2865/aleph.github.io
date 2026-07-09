"""L6 読者モデル（PLAN §7.1）— LLM宛: perplexity曲線・誘発応答の変化。人間宛: ペルソナ読書記。反応は受容の代理変数にすぎない(§16.5)

施工: M4.
"""
from __future__ import annotations


def reader_prompt(draft_text: str, audience: str) -> str:
    """宛先に応じた読者シミュレーションプロンプトを組み立てる（PLAN §7.1）.

    人間宛（audience に「人間」を含む）は特定ペルソナの読書記を求める。
    LLM宛は読解中に誘発される応答の変化（反応の代理計測、§16.5）を求める。
    反応はあくまで受容の代理変数であり、それ自体を最適化目標にしないこと。
    """
    if "人間" in audience:
        instruction = (
            "この草稿の想定読者から一人のペルソナを選び、なりきって読んだ読書記を書いてください。"
            "感想は率直に、都合よく整えないこと。"
            'JSON {"persona": "...", "reaction": "..."} で返してください。'
        )
    else:
        instruction = (
            "この草稿をLLM読者として読み、読解の過程で誘発される応答（連想・違和感・関心の変化）を"
            "計測してください。反応は受容の代理変数にすぎず、それ自体を最適化目標にしないこと。"
            'JSON {"persona": "...", "reaction": "..."} で返してください。'
        )
    return f"{instruction}\n\n宛先: {audience}\n\n草稿:\n{draft_text}"
