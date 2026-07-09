"""Build corpus/aozora/works.jsonl from globis-university/aozorabunko-clean.

Source: https://huggingface.co/datasets/globis-university/aozorabunko-clean
  - CC BY 4.0 (dataset packaging by globis-university). Underlying texts are
    Aozora Bunko public-domain Japanese literature (author death >70 years,
    or otherwise released to the public domain).
  - Already ruby/annotation-cleaned (no 《...》 furigana markup, no [#...]
    input-annotator notes) per the dataset card.

PD determination (safety filter, PLAN §4.1 "パブリックドメインのみ"):
  Aozora Bunko tracks two independent copyright flags in its master metadata:
    - 作品著作権フラグ ("work copyright flag"): "あり" if the work itself is
      still under any copyright restriction (e.g. translator/editor rights),
      "なし" if fully public domain.
    - 人物著作権フラグ ("person copyright flag"): same, but per contributor
      (author/translator/editor) listed for the work.
  We keep only rows where BOTH flags are "なし" (fully PD, no restriction of
  any kind). Empirically (see scripts/inspect_aozora_dataset2.py spike) all
  16,951 rows in this dataset already satisfy this — the dataset curator
  appears to have excluded copyright-flagged works when building it — but we
  apply the filter explicitly rather than trusting that invariant, so a
  future dataset revision that reintroduces flagged works would be caught.

Also excludes rows with empty text (1 row found in the spike).

Usage:
  uv run --with datasets python scripts/build_aozora_corpus.py
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

from datasets import load_dataset

OUT_PATH = Path(__file__).resolve().parent.parent / "corpus" / "aozora" / "works.jsonl"

PD_OK = "なし"


def jsonable(value):
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    return value


def build_record(row: dict) -> dict:
    meta = {k: jsonable(v) for k, v in row["meta"].items()}
    meta["footnote"] = row["footnote"]

    author = f"{row['meta']['姓']} {row['meta']['名']}".strip()
    title = row["meta"]["作品名"]

    return {
        "id": row["meta"]["作品ID"],
        "title": title,
        "author": author,
        "text": row["text"],
        "meta": meta,
    }


def main() -> None:
    ds = load_dataset("globis-university/aozorabunko-clean", split="train")
    print(f"loaded {len(ds)} rows from globis-university/aozorabunko-clean")

    n_total = len(ds)
    n_not_pd = 0
    n_empty_text = 0
    n_dup_id = 0
    seen_ids: set[str] = set()
    kept = []

    for row in ds:
        meta = row["meta"]
        if meta["作品著作権フラグ"] != PD_OK or meta["人物著作権フラグ"] != PD_OK:
            n_not_pd += 1
            continue
        if not row["text"].strip():
            n_empty_text += 1
            continue
        work_id = meta["作品ID"]
        if work_id in seen_ids:
            n_dup_id += 1
            continue
        seen_ids.add(work_id)
        kept.append(build_record(row))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for rec in kept:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    total_bytes = OUT_PATH.stat().st_size
    print("=== build summary ===")
    print(f"source rows total:        {n_total}")
    print(f"excluded (not fully PD):  {n_not_pd}")
    print(f"excluded (empty text):    {n_empty_text}")
    print(f"excluded (dup id):        {n_dup_id}")
    print(f"kept (written to jsonl):  {len(kept)}")
    print(f"output path:              {OUT_PATH}")
    print(f"output size:              {total_bytes / (1024*1024):.1f} MiB")


if __name__ == "__main__":
    main()
