"""ALEPH CLI（PLAN §9）: aleph new / run / status / resume / publish.

施工: M0（骨格）。各コマンドの実体は該当マイルストーンで接続する。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aleph.core.budget import Budget
from aleph.core.config import load_config
from aleph.core.llm import CallLogger, Message, Router
from aleph.explore.atlas import build_atlas
from aleph.explore.corpus import LlamaServerEmbedder, ingest
from aleph.explore.niche import find_niches, report
from aleph.explore.webresearch import search, web_check


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aleph", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("new", help="種(seed)から新しい作品を開始する")
    sub.add_parser("run", help="閉ループを実行する（チェックポイントから継続）")
    sub.add_parser("status", help="予算3系統と進行中の作品を表示する")
    sub.add_parser("resume", help="クラッシュ後の再開（決定論的リプレイ）")
    sub.add_parser("publish", help="公開ゲートを起動する（初回は人間承認必須）")
    explore = sub.add_parser("explore", help="コーパスからアトラスとニッチ候補を構築する")
    explore.add_argument("--corpus", default="corpus/aozora/works.jsonl")
    explore.add_argument("--out", default="state/atlas")
    explore.add_argument("--report", default="state/atlas/niche_report.md")
    explore.add_argument("--limit", type=int)
    explore.add_argument("--top-n", type=int, default=20)
    explore.add_argument("--max-chunks-per-work", type=int, default=30)
    explore.add_argument("--skip-web", action="store_true")
    explore.add_argument("--reingest", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "status":
        root = Path(__file__).resolve().parent.parent
        config = load_config(root)
        budget = Budget(config)
        units = {"api": "USD", "harness": "calls", "local": "gpu_hours"}
        for ledger, values in budget.status().items():
            print(
                f"{ledger}: {values['spent']}/{values['limit']} "
                f"{units[ledger]} (period={values['period']})"
            )
        return 0
    if args.command == "explore":
        root = Path(__file__).resolve().parent.parent
        out_dir = Path(args.out)
        cfg = load_config(root)
        logger = CallLogger(out_dir / "calls.jsonl", secrets=cfg.secrets.values())
        budget = Budget(cfg)
        router = Router(cfg, logger, budget)
        scout = lambda prompt: router.call(  # noqa: E731 - 仕様上の配線をそのまま表す
            "scout",
            [Message("user", prompt)],
            max_tokens=1024,
        ).text

        provider = cfg.models["providers"]["llamacpp"]
        embedder_role = cfg.models["roles"]["embedder"]
        embedder = LlamaServerEmbedder(
            base_url=provider["base_url"],
            model=embedder_role["model"],
        )
        manifest = out_dir / "manifest.json"
        if args.reingest or not manifest.exists():
            print("explore: ingesting corpus", file=sys.stderr)
            stats = ingest(
                Path(args.corpus),
                out_dir,
                embedder,
                max_chunks_per_work=args.max_chunks_per_work,
                limit=args.limit,
            )
            print(
                f"explore: ingested {stats.n_works} works / {stats.n_chunks} chunks",
                file=sys.stderr,
            )
        else:
            print("explore: existing index found; skipping ingest", file=sys.stderr)

        print("explore: building atlas", file=sys.stderr)
        atlas = build_atlas(out_dir)
        web_checker = None
        api_key = cfg.secrets.get("BRAVE_API_KEY")
        if api_key and not args.skip_web:
            def web_checker(niche):
                return web_check(
                    niche,
                    lambda query, count=5: search(query, api_key=api_key, count=count),
                    scout,
                )

        print("explore: finding niches", file=sys.stderr)
        niches = find_niches(atlas, scout, top_n=args.top_n, web_checker=web_checker)
        report(niches, Path(args.report), top_n=args.top_n)
        print(f"explore: wrote {len(niches)} niches to {args.report}", file=sys.stderr)
        return 0
    print(f"aleph {args.command}: M0 施工対象（PLAN §10）", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
