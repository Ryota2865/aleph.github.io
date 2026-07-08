"""ALEPH CLI（PLAN §9）: aleph new / run / status / resume / publish.

施工: M0（骨格）。各コマンドの実体は該当マイルストーンで接続する。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aleph.core.budget import Budget
from aleph.core.config import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aleph", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("new", help="種(seed)から新しい作品を開始する")
    sub.add_parser("run", help="閉ループを実行する（チェックポイントから継続）")
    sub.add_parser("status", help="予算3系統と進行中の作品を表示する")
    sub.add_parser("resume", help="クラッシュ後の再開（決定論的リプレイ）")
    sub.add_parser("publish", help="公開ゲートを起動する（初回は人間承認必須）")
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
    print(f"aleph {args.command}: M0 施工対象（PLAN §10）", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
