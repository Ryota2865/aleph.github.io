"""L6 敵対的査読（PLAN §7.1）— 既視性の専任攻撃。Web再検索で既視感のある反復を url+理由つきで指摘する。

施工: M4.
"""
from __future__ import annotations

import json
from typing import Callable

from aleph.core.model_output import parse_model_output


def adversary_review(
    draft_text: str,
    summary: str,
    search_fn: Callable[..., list[dict]],
    scout: Callable[[str], str],
) -> dict:
    """草稿概要でWeb再検索し、ヒットをscoutに提示して既視性を敵対的に判定する.

    返り値: {"derivative": bool, "evidence": [{"url", "title", "reason"}, ...]}
    derivative=True のときのみ evidence を埋める（ヒット由来のurl/titleに
    scoutの判定理由をreasonとして添える）。
    """
    hits = search_fn(summary)
    bibliography = [
        {
            "title": str(hit.get("title", "")),
            "url": str(hit.get("url", "")),
            "snippet": str(hit.get("snippet", ""))[:500],
        }
        for hit in hits
    ]
    prompt = (
        "以下の草稿が、検索結果に示された既存作品の焼き直し（既視感のある反復）でないか、"
        "敵対的な立場で厳しく判定してください。"
        'JSON {"exists": true|false, "rationale": "..."} で返してください。\n'
        f"草稿概要: {summary}\n"
        f"検索結果: {json.dumps(bibliography, ensure_ascii=False)}\n"
        f"草稿冒頭: {draft_text[:1000]}"
    )
    response = scout(prompt)
    parsed = parse_model_output(response, schema=dict).value or {}
    derivative = parsed.get("exists") is True
    rationale = str(parsed.get("rationale", response))
    evidence: list[dict] = []
    if derivative:
        evidence = [
            {
                "url": str(hit.get("url", "")),
                "title": str(hit.get("title", "")),
                "reason": rationale,
            }
            for hit in hits
        ]
    return {"derivative": derivative, "evidence": evidence}
