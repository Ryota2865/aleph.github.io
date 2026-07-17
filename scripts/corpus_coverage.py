"""C-1: アトラス属性被覆マップ（designs/corpus-expansion.md C-1・PLAN_CHANGELOG 0.7.18 問4）.

永続化済みのクラスタ属性注釈（aleph.explore.atlas.annotate_clusters が書く
cluster_annotations.json）を集計し、theme/form/viewpoint/era の4軸で
何が観測されているか・組み合わせがどれだけ埋まっているかを reports/ へ書き出す。
「測ってから買う」規律（実験C/D/Eと同じ）——コーパス拡張の前に、まず現状の被覆を測る。

Usage:
  # 1) まだ cluster_annotations.json が無ければ先に生成する
  uv run python scripts/annotate_atlas_clusters.py --index state/atlas
  # 2) 被覆マップを書き出す
  uv run python scripts/corpus_coverage.py --index state/atlas
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

AXES = ("theme", "form", "viewpoint", "era")


def compute_coverage(annotations: list[dict]) -> dict:
    """クラスタ属性注釈のリストから被覆統計を計算する.

    unannotated_clusters（attributes=None＝scout応答が解釈不能だった等）と
    low_confidence_clusters（confidence<0.5）は、被覆マップの信頼性を読者が
    判断できるよう明示する（単一注釈器の分類であることの開示、Q4決定）。
    """
    total = len(annotations)
    annotated = [a for a in annotations if a.get("attributes")]
    low_confidence = [a for a in annotated if (a.get("confidence") or 0.0) < 0.5]

    axis_values: dict[str, Counter] = {axis: Counter() for axis in AXES}
    occupied: set[tuple[str, ...]] = set()
    for record in annotated:
        attrs = record["attributes"]
        combo = tuple(str(attrs[axis]) for axis in AXES)
        occupied.add(combo)
        for axis in AXES:
            axis_values[axis][str(attrs[axis])] += 1

    possible_combinations = 1
    for axis in AXES:
        possible_combinations *= max(len(axis_values[axis]), 1)

    return {
        "total_clusters": total,
        "annotated_clusters": len(annotated),
        "unannotated_clusters": total - len(annotated),
        "low_confidence_clusters": len(low_confidence),
        "axis_values": {axis: dict(counter.most_common()) for axis, counter in axis_values.items()},
        "occupied_combinations": sorted(occupied),
        "possible_combinations": possible_combinations,
        "coverage_ratio": (len(occupied) / possible_combinations) if possible_combinations else 0.0,
    }


def write_report(coverage: dict, path: Path, *, source: Path, annotator_models: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# 属性被覆マップ {datetime.now().strftime('%Y-%m-%d')}",
        "",
        f"- 索引: `{source}`",
        f"- 注釈モデル: {', '.join(sorted(set(annotator_models))) or '(不明)'}",
        f"- 総クラスタ数: {coverage['total_clusters']}"
        f"（注釈成功 {coverage['annotated_clusters']} / 未注釈 {coverage['unannotated_clusters']}"
        f" / 低信頼(confidence<0.5) {coverage['low_confidence_clusters']}）",
        f"- 占有組み合わせ: {len(coverage['occupied_combinations'])} / "
        f"理論上の全組み合わせ {coverage['possible_combinations']}"
        f"（被覆率 {coverage['coverage_ratio']:.4f}）",
        "",
        "**注記**: 本マップは単一注釈器（上記モデル）による分類である。属性ラベルは",
        "「地図の事実」ではなく、この注釈器の判断である（PLAN_CHANGELOG 0.7.18 問4）。",
        "",
        "## 軸別の観測値",
        "",
    ]
    for axis in AXES:
        values = coverage["axis_values"][axis]
        lines.append(f"### {axis}（{len(values)}種）")
        lines.append("")
        for value, count in values.items():
            lines.append(f"- {value}: {count}クラスタ")
        lines.append("")

    lines.append("## 占有済みの組み合わせ")
    lines.append("")
    lines.append("| " + " | ".join(AXES) + " |")
    lines.append("|" + "---|" * len(AXES))
    for combo in coverage["occupied_combinations"]:
        lines.append("| " + " | ".join(combo) + " |")

    lines.extend([
        "",
        "## 所見",
        "",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=Path("state/atlas"), help="アトラス索引ディレクトリ")
    parser.add_argument(
        "--out", type=Path, default=None,
        help="出力レポートパス（既定: reports/CORPUS_COVERAGE_<today>.md）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from aleph.explore.atlas import load_cluster_annotations

    annotations = load_cluster_annotations(args.index)
    if not annotations:
        print(
            f"corpus_coverage: {args.index}/cluster_annotations.json が見つからない。"
            "先に annotate_clusters（例: scripts/annotate_atlas_clusters.py）を実行すること。",
            file=sys.stderr,
        )
        return 1

    coverage = compute_coverage(annotations)
    out = args.out or Path("reports") / f"CORPUS_COVERAGE_{datetime.now().strftime('%Y%m%d')}.md"
    annotator_models = [str(a.get("annotator_model", "")) for a in annotations if a.get("annotator_model")]
    write_report(coverage, out, source=args.index, annotator_models=annotator_models)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
