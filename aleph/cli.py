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


def _next_work_id(works_root: Path) -> str:
    """works/ 直下の連番id（w0001 形式）の次を算出する."""
    works_root = Path(works_root)
    highest = 0
    if works_root.exists():
        for entry in works_root.iterdir():
            if not entry.is_dir() or not entry.name.startswith("w"):
                continue
            try:
                highest = max(highest, int(entry.name[1:]))
            except ValueError:
                continue
    return f"w{highest + 1:04d}"


def _budget_state_path(root: Path) -> Path:
    return Path(root) / "state" / "budget.json"


def _work_for_cli(works_root: Path, work_id: str, config):
    from aleph.core.artifacts import Work

    return Work(works_root, work_id, secrets=config.secrets.values())


def _cmd_run(root: Path, args) -> int:
    """aleph run: 実LLM依存を組み立てて pipeline.run_work を呼ぶ（M6 配線）."""
    from aleph.explore.corpus import LlamaServerEmbedder
    from aleph.pipeline import RealDeps, run_work

    config = load_config(root)
    work = _work_for_cli(root / "works", args.work, config)
    if not work.dir.exists():
        print(f"run: work not found: {work.dir}", file=sys.stderr)
        return 1

    logger = CallLogger(work.calls, secrets=config.secrets.values())
    budget = Budget(config, state_path=_budget_state_path(root))
    router = Router(config, logger, budget)

    embedder = None
    embedder_role = config.models.get("roles", {}).get("embedder")
    llamacpp = config.models.get("providers", {}).get("llamacpp")
    if embedder_role and llamacpp:
        try:
            embedder = LlamaServerEmbedder(
                base_url=llamacpp["base_url"], model=embedder_role["model"],
            )
        except Exception as exc:  # 埋め込み取得失敗は空リストで凌ぐ（M6 最小配線）
            print(f"run: embedder unavailable ({exc}); continuing without", file=sys.stderr)

    api_key = config.secrets.get("BRAVE_API_KEY")

    def search_fn(query, count=5):
        if not api_key:
            return []
        try:
            return search(query, api_key=api_key, count=count)
        except Exception:
            return []

    deps = RealDeps(
        work, router, config=config, index_dir=root / args.index,
        search_fn=search_fn, embedder=embedder,
        force_audience=getattr(args, "force_audience", None),
    )
    final = run_work(work, deps, decided_by="cli-run")
    print(f"run: {args.work} -> {final.value}", file=sys.stderr)
    return 0


def _cmd_publish(root: Path, args) -> int:
    """aleph publish: 棚上げ済み(または完成)作品の公開ゲートを再評価する（PLAN §9）.

    初回公開の人間承認は config/policies.yaml の publication.first_publish_ack で行う。
    SHELVE/FINISH のチェックポイントを FINISH に戻して FINISH→(PUBLISH|SHELVE) ゲートを
    再実行する（w0004 公開で手動化していた手順の正規化。0.7.14）。
    """
    from aleph.core.loop import Checkpoint, State
    from aleph.pipeline import RealDeps, run_work

    config = load_config(root)
    work = _work_for_cli(root / "works", args.work, config)
    if not work.dir.exists():
        print(f"publish: work not found: {work.dir}", file=sys.stderr)
        return 1
    try:
        cp = Checkpoint.load(work.dir)
    except FileNotFoundError:
        print(f"publish: no checkpoint for {args.work}; run it to completion first", file=sys.stderr)
        return 1

    if cp.state == State.PUBLISH:
        print(f"publish: {args.work} is already published", file=sys.stderr)
        return 0
    if cp.state == State.DISCARD:
        print(f"publish: {args.work} was discarded; refusing to publish", file=sys.stderr)
        return 1
    if cp.state not in (State.SHELVE, State.FINISH):
        print(
            f"publish: {args.work} is not finished (state={cp.state.value}); run it first",
            file=sys.stderr,
        )
        return 1

    ack = bool(config.policies.get("publication", {}).get("first_publish_ack", False))
    if not ack:
        print(
            "publish: publication.first_publish_ack=false. "
            "初回公開は人間承認が必要です。config/policies.yaml を true にして再実行してください。",
            file=sys.stderr,
        )
        return 1

    # SHELVE/FINISH → FINISH に戻し、公開ゲートを再評価させる（正典遷移 FINISH→PUBLISH は有効）。
    Checkpoint(
        work_id=cp.work_id, state=State.FINISH, step=max(0, cp.step - 1), payload=dict(cp.payload),
    ).save(work.dir)

    logger = CallLogger(work.calls, secrets=config.secrets.values())
    budget = Budget(config, state_path=_budget_state_path(root))
    router = Router(config, logger, budget)
    deps = RealDeps(
        work, router, config=config, index_dir=root / args.index, search_fn=lambda *a, **k: [],
    )
    final = run_work(work, deps, decided_by="cli-publish")
    print(f"publish: {args.work} -> {final.value}", file=sys.stderr)
    return 0 if final == State.PUBLISH else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aleph", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    new_p = sub.add_parser("new", help="種(seed)から新しい作品を開始する")
    new_p.add_argument("--hint", default="", help="種となる着想のテキスト")
    run_p = sub.add_parser("run", help="閉ループを実行する（チェックポイントから継続）")
    run_p.add_argument("--work", required=True, help="作品id（works/<id>）")
    run_p.add_argument("--index", default="state/atlas", help="探索・素材索引のディレクトリ")
    run_p.add_argument(
        "--force-audience", default=None,
        help="L1の自律選択を上書きし宛先配合を固定する実験用（例 'LLM 0.6 / 自分 0.25 / 人間 0.15'）。"
        "指定時 L1 は choose_intent を呼ばず owner-experiment 決定として記録する（PLAN §3・0.7.14）",
    )
    sub.add_parser("status", help="予算3系統と進行中の作品を表示する")
    sub.add_parser("resume", help="クラッシュ後の再開（決定論的リプレイ）")
    pub_p = sub.add_parser("publish", help="棚上げ済み作品の公開ゲートを再評価する（初回は人間承認必須）")
    pub_p.add_argument("--work", required=True, help="作品id（works/<id>）")
    pub_p.add_argument("--index", default="state/atlas", help="索引ディレクトリ（公開ゲートは未使用だが依存配線に必要）")
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
    root = Path(__file__).resolve().parent.parent
    if args.command == "new":
        works_root = root / "works"
        works_root.mkdir(parents=True, exist_ok=True)
        config = load_config(root)
        work_id = _next_work_id(works_root)
        work = _work_for_cli(works_root, work_id, config)
        work.create({"hint": args.hint} if args.hint else {})
        print(f"new: created {work_id} at {work.dir}", file=sys.stderr)
        return 0
    if args.command == "run":
        return _cmd_run(root, args)
    if args.command == "publish":
        return _cmd_publish(root, args)
    if args.command == "status":
        config = load_config(root)
        budget = Budget(config, state_path=_budget_state_path(root))
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
        budget = Budget(cfg, state_path=_budget_state_path(root))
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

        # アトラス成果物が揃っていれば再構築せず読み込む（HDBSCANは90kチャンクで
        # 長時間かかるため。--reingest 時のみ作り直す）
        atlas_ready = all(
            (out_dir / name).exists()
            for name in ("labels.npy", "density.npy", "style.npy", "atlas_meta.json")
        )
        if atlas_ready and not args.reingest:
            from aleph.explore.atlas import Atlas

            print("explore: loading existing atlas", file=sys.stderr)
            atlas = Atlas.load(out_dir)
        else:
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
