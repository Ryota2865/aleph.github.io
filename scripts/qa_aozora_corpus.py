"""QA pass over corpus/aozora/works.jsonl: schema check, random sampling, and a
basic mojibake / leftover-markup scan.

Run with: uv run python scripts/qa_aozora_corpus.py
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "corpus" / "aozora" / "works.jsonl"
REQUIRED_TOP_KEYS = {"id", "title", "author", "text", "meta"}
RUBY_ARTIFACT_RE = re.compile(r"｜|［＃|\[#")


def main() -> None:
    lines = PATH.read_text(encoding="utf-8").splitlines()
    print(f"total lines: {len(lines)}")

    random.seed(42)
    sample_idx = sorted(random.sample(range(len(lines)), 5))

    n_schema_bad = 0
    ids = set()
    n_dup = 0
    for i, line in enumerate(lines):
        rec = json.loads(line)
        if set(rec.keys()) != REQUIRED_TOP_KEYS:
            n_schema_bad += 1
        if rec["id"] in ids:
            n_dup += 1
        ids.add(rec["id"])
        if i in sample_idx:
            print("=" * 60)
            print("id:", rec["id"], "| title:", rec["title"], "| author:", rec["author"])
            print("text head (200 chars):", repr(rec["text"][:200]))
            print("meta 文字遣い種別:", rec["meta"].get("文字遣い種別"))
            print("meta 作品著作権フラグ:", rec["meta"].get("作品著作権フラグ"))
            print("meta 人物著作権フラグ:", rec["meta"].get("人物著作権フラグ"))
            print("meta 生年月日/没年月日:", rec["meta"].get("生年月日"), "/", rec["meta"].get("没年月日"))
            print("meta 底本名1:", rec["meta"].get("底本名1"))
            hit = RUBY_ARTIFACT_RE.search(rec["text"])
            print("leftover ruby/annotation artifact found:", bool(hit))

    print("=" * 60)
    print("schema violations:", n_schema_bad)
    print("duplicate ids:", n_dup)
    print("unique ids:", len(ids))


if __name__ == "__main__":
    main()
