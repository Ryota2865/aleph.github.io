"""C-1改訂版（後半）: 作品単位の層化サンプリング注釈（PLAN_CHANGELOG 0.7.19 問2）.

被覆の主測定。クラスタ単位の注釈（annotate_atlas_clusters.py）はノイズ約9割を
被覆計算から落とすため、本スクリプトは**作品単位の層化標本**に対して scout が
主題・形式・視点の三軸を注釈する（era・言語は台帳直接計算 `corpus_coverage_metadata.py`
が真値を持つので、ここでは注釈しない——「持っている真値を推定し直さない」）。

層化設計:
- 層 = 著者没年の年代（台帳真値）。各層へ比例配分（最小1作品）。
- 著者上限 = 同一著者から最大2作品（多作著者への標本の占拠を防ぐ）。
- ノイズ点の包含 = 各作品についてアトラス上のノイズ・チャンク比率を記録し、
  ノイズ多数派の作品が標本に含まれることを検査・報告する（sol/Fable5の要求）。

出力: `state/atlas/work_annotations.json`（annotator_model・prompt_version・
confidence・ts・層情報つき。単一注釈器による分類であることを明示）。

Usage:
  uv run python scripts/annotate_work_sample.py --n 200
  uv run python scripts/corpus_coverage_sample.py   # 集計は別スクリプト
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROMPT_VERSION = "work-sample-v1"
AXES = ("theme", "form", "viewpoint")


def death_decade(meta: dict) -> str:
    head = (meta.get("没年月日") or "")[:4]
    return f"{int(head) // 10 * 10}s" if head.isdigit() else "unknown"


def stratified_sample(
    works: list[dict],
    *,
    n_target: int = 200,
    per_author_cap: int = 2,
    seed: int = 42,
) -> list[dict]:
    """作品リスト（id/author/death_decade/noise_share を持つdict）から層化標本を作る.

    層=death_decade、比例配分（最小1）、著者上限つき。決定論（seed固定）。
    """
    rng = random.Random(seed)
    strata: dict[str, list[dict]] = defaultdict(list)
    for w in works:
        strata[w["death_decade"]].append(w)
    total = sum(len(v) for v in strata.values())
    sample: list[dict] = []
    for decade in sorted(strata, key=lambda d: -len(strata[d])):
        members = strata[decade][:]
        rng.shuffle(members)
        quota = max(1, round(n_target * len(members) / total))
        picked: list[dict] = []
        author_count: Counter = Counter()
        for w in members:
            if len(picked) >= quota:
                break
            if author_count[w["author"]] >= per_author_cap:
                continue
            author_count[w["author"]] += 1
            picked.append(w)
        sample.extend(picked)
    return sample


def noise_share_by_work(index_dir: Path) -> dict[str, float]:
    """chunks.jsonl と labels.npy から、作品ごとのノイズ・チャンク比率を計算する."""
    import numpy as np

    labels = np.load(index_dir / "labels.npy")
    totals: Counter = Counter()
    noise: Counter = Counter()
    with open(index_dir / "chunks.jsonl", encoding="utf-8") as f:
        for i, line in enumerate(f):
            wid = json.loads(line)["work_id"]
            totals[wid] += 1
            if labels[i] < 0:
                noise[wid] += 1
    return {wid: noise[wid] / totals[wid] for wid in totals}


def annotate_works(sample: list[dict], texts: dict[str, str], scout, *,
                   annotator_model: str, max_chars: int = 1500) -> list[dict]:
    from aleph.explore.niche import _extract_json_object

    records: list[dict] = []
    for w in sample:
        excerpt = (texts.get(w["id"]) or "")[:max_chars]
        response = scout(
            "次の作品冒頭を、主題(theme)・形式(form)・視点(viewpoint)の三軸で"
            "属性ラベリングしてください。時代は問いません（書誌から別途計算するため）。"
            "併せて、この分類にどれだけ自信があるかを0.0〜1.0のconfidenceとして"
            "自己申告してください。"
            'JSON {"theme":"...","form":"...","viewpoint":"...","confidence":0.0} '
            "だけを返してください。\n"
            f"題: {w.get('title', '')} / 著者: {w.get('author', '')}\n---\n{excerpt}"
        )
        parsed = _extract_json_object(response) or {}
        record = {
            "work_id": w["id"],
            "title": w.get("title"),
            "author": w.get("author"),
            "death_decade": w["death_decade"],
            "noise_share": w.get("noise_share"),
            "annotator_model": annotator_model,
            "prompt_version": PROMPT_VERSION,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if parsed and all(parsed.get(axis) for axis in AXES):
            record["attributes"] = {axis: str(parsed[axis]) for axis in AXES}
            try:
                record["confidence"] = float(parsed.get("confidence"))
            except (TypeError, ValueError):
                record["confidence"] = None
        else:
            record["attributes"] = None
            record["confidence"] = None
        records.append(record)
    return records


def _load_works_for_sampling(corpus_path: Path, index_dir: Path) -> tuple[list[dict], dict[str, str]]:
    noise = noise_share_by_work(index_dir)
    works: list[dict] = []
    texts: dict[str, str] = {}
    with open(corpus_path, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            works.append({
                "id": row["id"],
                "title": row.get("title"),
                "author": row.get("author"),
                "death_decade": death_decade(row["meta"]),
                "noise_share": noise.get(row["id"]),
            })
            texts[row["id"]] = row.get("text", "")[:2000]
    return works, texts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "corpus/aozora/works.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "state" / "atlas")
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--calls-log", type=Path, default=Path("/tmp/aleph_c1_sample_calls.jsonl"))
    args = parser.parse_args(argv)

    from annotate_atlas_clusters import build_scout

    works, texts = _load_works_for_sampling(args.corpus, args.index)
    sample = stratified_sample(works, n_target=args.n, seed=args.seed)
    noise_majority = sum(1 for w in sample if (w.get("noise_share") or 0) > 0.5)
    print(f"sample: {len(sample)} works ({noise_majority} noise-majority)", flush=True)

    scout, model = build_scout(ROOT, args.calls_log, work_id="exp-c1-sample")
    records = annotate_works(sample, texts, scout, annotator_model=model)

    payload = {
        "prompt_version": PROMPT_VERSION,
        "annotator_model": model,
        "created": datetime.now(timezone.utc).isoformat(),
        "sampling": {
            "n_target": args.n,
            "seed": args.seed,
            "strata": "author_death_decade",
            "per_author_cap": 2,
            "noise_majority_works": noise_majority,
        },
        "annotations": records,
    }
    out = args.index / "work_annotations.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = sum(1 for r in records if r.get("attributes"))
    print(f"annotated {ok}/{len(records)} works -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
