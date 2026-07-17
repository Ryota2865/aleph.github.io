"""アトラスの全クラスタへ属性注釈を付け、cluster_annotations.jsonへ永続化する.

PLAN_CHANGELOG 0.7.18 問4・designs/corpus-expansion.md C-1の前段。scout役はRouter経由
（既定はconfig/models.yamlのscoutロール、通常はローカルllama-swap）。

Usage:
  uv run python scripts/annotate_atlas_clusters.py --index state/atlas
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_scout(root: Path, calls_log: Path, *, work_id: str = "exp-c1-annotate"):
    from aleph.core.budget import Budget
    from aleph.core.config import load_config
    from aleph.core.llm import CallLogger, Message, Router
    from aleph.core.local import LocalRuntime

    config = load_config(root)
    logger = CallLogger(calls_log, secrets=config.secrets.values())
    budget = Budget(config)
    router = Router(config, logger, budget, local_runtime=LocalRuntime(config))
    model = config.models["roles"]["scout"]["model"]

    def scout(prompt: str) -> str:
        return router.call("scout", [Message("user", prompt)], work_id=work_id).text

    return scout, model


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=ROOT / "state" / "atlas")
    parser.add_argument("--calls-log", type=Path, default=Path("/tmp/aleph_c1_annotate_calls.jsonl"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from aleph.explore.atlas import Atlas, annotate_clusters

    atlas = Atlas.load(args.index)
    scout, model = build_scout(ROOT, args.calls_log)
    annotations = annotate_clusters(atlas, scout, annotator_model=model)
    n_ok = sum(1 for a in annotations if a.get("attributes"))
    print(f"annotated {n_ok}/{len(annotations)} clusters -> {args.index}/cluster_annotations.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
