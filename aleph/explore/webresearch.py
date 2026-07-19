"""L2 Webリサーチ（PLAN §4.4）— Brave照合と短片の素材カード化."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Callable

import httpx

from aleph.core.model_output import parse_model_output


_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
_search_lock = threading.Lock()
_last_search_at = 0.0


class WebResearchError(RuntimeError):
    pass


@dataclass(frozen=True)
class WebCheckResult:
    excluded: bool
    prior_examples: list[dict]
    rationale: str


def search(query: str, *, api_key: str, count: int = 5) -> list[dict]:
    """Brave Searchを無料枠の1rps以内で呼び出す."""
    global _last_search_at
    with _search_lock:
        wait = 1.1 - (time.monotonic() - _last_search_at)
        if wait > 0:
            time.sleep(wait)
        _last_search_at = time.monotonic()
        try:
            response = httpx.get(
                _SEARCH_URL,
                headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                params={"q": query, "count": count},
                timeout=30.0,
            )
            response.raise_for_status()
            results = response.json().get("web", {}).get("results", [])
        except Exception:
            # APIキーやレスポンス本文を例外連鎖へ載せない（PLAN §14.2）。
            raise WebResearchError("Brave Search request failed") from None
    return [
        {
            "title": str(item.get("title", "")),
            "url": str(item.get("url", "")),
            "snippet": str(item.get("description", item.get("snippet", ""))),
        }
        for item in results[:count]
    ]


def to_material_card(hit: dict) -> dict:
    """検索結果を、保護本文を保持しない短片+書誌の素材カードへ変換する."""
    return {
        "content": str(hit.get("snippet", ""))[:500],
        "source": {
            "url": str(hit.get("url", "")),
            "title": str(hit.get("title", "")),
        },
        "method": "webresearch",
        "tags": ["prior_art"],
    }


def web_check(
    niche: dict,
    search_fn: Callable[..., list[dict]],
    scout: Callable[[str], str],
) -> WebCheckResult:
    """候補と同種の先行作品が実在するか、検索結果をscoutで確認する."""
    hits = search_fn(niche.get("description", ""), count=5)
    bibliography = [
        {
            "title": str(hit.get("title", "")),
            "url": str(hit.get("url", "")),
            "snippet": str(hit.get("snippet", ""))[:500],
        }
        for hit in hits
    ]
    response = scout(
        "候補ニッチと同種の作品が検索結果に既に存在するか判定してください。"
        'JSON {"exists": true|false, "rationale": "..."} で返してください。\n'
        f"候補: {niche.get('description', '')}\n"
        f"検索結果: {json.dumps(bibliography, ensure_ascii=False)}"
    )
    parsed = parse_model_output(response, schema=dict).value or {}
    exists = parsed.get("exists") is True
    rationale = str(parsed.get("rationale", response))
    prior_examples = [to_material_card(hit) for hit in hits] if exists else []
    return WebCheckResult(
        excluded=exists,
        prior_examples=prior_examples,
        rationale=rationale,
    )
