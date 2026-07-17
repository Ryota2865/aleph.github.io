"""C-1改訂版（後半）: 層化標本注釈の集計 → 被覆の標本推定レポート.

`annotate_work_sample.py` が書いた `work_annotations.json` を集計し、
主題・形式・視点の観測分布と組み合わせ占有を**標本推定**として報告する。
era は各作品の台帳真値（没年年代）を層として併記する。全数の真値は
`corpus_coverage_metadata.py`（台帳直接計算）が持つ——役割分担を混ぜない。

Usage:
  uv run python scripts/corpus_coverage_sample.py --index state/atlas
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

AXES = ("theme", "form", "viewpoint")


def aggregate_sample(annotations: list[dict]) -> dict:
    """作品注釈のリストから標本被覆統計を計算する。欠測は欠測として報告する."""
    total = len(annotations)
    annotated = [a for a in annotations if a.get("attributes")]
    low_confidence = [a for a in annotated if (a.get("confidence") or 0.0) < 0.5]
    noise_majority = [a for a in annotations if (a.get("noise_share") or 0.0) > 0.5]

    axis_values: dict[str, Counter] = {axis: Counter() for axis in AXES}
    occupied: set[tuple[str, ...]] = set()
    era_theme: Counter = Counter()
    for record in annotated:
        attrs = record["attributes"]
        occupied.add(tuple(str(attrs[axis]) for axis in AXES))
        for axis in AXES:
            axis_values[axis][str(attrs[axis])] += 1
        era_theme[(record.get("death_decade", "unknown"), str(attrs["theme"]))] += 1

    return {
        "total_works": total,
        "annotated_works": len(annotated),
        "unannotated_works": total - len(annotated),
        "low_confidence_works": len(low_confidence),
        "noise_majority_works": len(noise_majority),
        "axis_values": {axis: dict(axis_values[axis]) for axis in AXES},
        "occupied_combinations": sorted(occupied),
        "era_theme": {f"{era} / {theme}": n for (era, theme), n in era_theme.most_common()},
    }


def render_report(stats: dict, meta: dict) -> str:
    lines = [
        f"# 属性被覆・層化標本推定 {datetime.now():%Y-%m-%d}",
        "",
        f"- 標本: {stats['total_works']} 作品（注釈成功 {stats['annotated_works']} / "
        f"未注釈 {stats['unannotated_works']} / 低信頼<0.5 {stats['low_confidence_works']}）",
        f"- ノイズ多数派作品（アトラス上でチャンクの過半がノイズ）: {stats['noise_majority_works']} 件"
        "——ノイズ点を被覆測定から落とさないという要求（0.7.19 問2）の充足を示す。",
        f"- 注釈器: {meta.get('annotator_model')}（prompt {meta.get('prompt_version')}、単一注釈器）",
        f"- 層化: {meta.get('sampling', {}).get('strata')}・著者上限 "
        f"{meta.get('sampling', {}).get('per_author_cap')}・seed {meta.get('sampling', {}).get('seed')}",
        "- **これは標本推定である**。era・言語・形式(NDC)の全数真値は"
        " `reports/CORPUS_COVERAGE_METADATA_*.md`（台帳直接計算）を参照。",
    ]
    for axis in AXES:
        values = stats["axis_values"][axis]
        lines.append(f"\n### {axis}（観測 {len(values)} 種）\n")
        lines.append("| 値 | 作品数 |")
        lines.append("|---|---|")
        for key, count in sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))[:25]:
            lines.append(f"| {key} | {count} |")
    lines.append(f"\n### 占有組み合わせ（theme×form×viewpoint）: {len(stats['occupied_combinations'])} 通り")
    lines.append("\n### era（台帳）× theme（注釈）上位\n")
    lines.append("| era / theme | 作品数 |")
    lines.append("|---|---|")
    for key, count in list(stats["era_theme"].items())[:20]:
        lines.append(f"| {key} | {count} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=ROOT / "state" / "atlas")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    payload = json.loads((args.index / "work_annotations.json").read_text(encoding="utf-8"))
    stats = aggregate_sample(payload.get("annotations", []))
    out = args.out or ROOT / f"reports/CORPUS_COVERAGE_SAMPLE_{datetime.now():%Y%m%d}.md"
    out.write_text(render_report(stats, payload), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
