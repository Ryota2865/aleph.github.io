"""AI紋の反復を検出し、削除ではなく配給へ回すための小さな査読補助."""
from __future__ import annotations

import re


_PATTERNS = (
    {
        "name": "〜ほど、〜",
        "regex": re.compile(r"ほど[、,]"),
        "threshold": 3,
    },
)


def overused_syntax_patterns(text: str) -> list[dict]:
    """高頻度の構文型を返す。数は診断用で、改稿指示では消去ではなく配給を求める."""
    findings: list[dict] = []
    for pattern in _PATTERNS:
        matches = list(pattern["regex"].finditer(text or ""))
        if len(matches) > int(pattern["threshold"]):
            findings.append({"name": pattern["name"], "count": len(matches)})
    return findings


def rationing_instructions(text: str) -> list[str]:
    """高頻度のAI紋を、特定人物・箇所へ限定する改稿指示に変換する."""
    instructions: list[str] = []
    for finding in overused_syntax_patterns(text):
        instructions.append(
            f"AI紋の配給: 構文型「{finding['name']}」を消すのではなく、特定の人物/箇所に限定せよ。"
        )
    return instructions
