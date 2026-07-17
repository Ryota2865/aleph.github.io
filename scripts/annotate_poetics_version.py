"""w0001-w0007へのpoetics_version遡及注釈（Fable 5審査、PLAN_CHANGELOG 0.7.18-1 問7-1）.

`aleph/meta/poetics.py::current_version()`配線（RealDeps.choose_intent）は
本改修以降の新規作品にのみ効く。w0001〜w0007は全て、詩学が2026-07-11の第0版生成
以来一度も改訂されていない期間に書かれたため、poetics_version=0で遡及注釈する。

一回限りの実行用（冪等: 既に注釈済みの作品はスキップ）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from aleph.core.artifacts import Work
from aleph.meta.poetics import current_version

ROOT = Path(__file__).resolve().parents[1]
POETICS_DIR = ROOT / "poetics"
TARGETS = ("w0001", "w0002", "w0003", "w0004", "w0005", "w0006", "w0007")


def _already_annotated(work: Work) -> bool:
    if not work.decisions.exists():
        return False
    return "poetics_version:" in work.decisions.read_text(encoding="utf-8")


def annotate(work_id: str, version: int) -> bool:
    work = Work(ROOT / "works", work_id)
    if _already_annotated(work):
        print(f"{work_id}: already annotated, skip")
        return False
    work.append_decision({
        "ts": datetime.now(timezone.utc).isoformat(),
        "layer": "L1",
        "decision": f"poetics_version:{version}",
        "reason": (
            "遡及注釈（PLAN_CHANGELOG 0.7.18-1、Fable 5審査 問7-1）。本作は"
            f"詩学第{version}版（poetics/poetics.md、2026-07-11生成の第0版から一度も"
            "改訂されていない期間）の下で書かれた。以後の詩学改訂と作品を縦断比較できる"
            "よう、通常配線（RealDeps._stamp_poetics_version）が新規作品へ自動的に刻む"
            "ものを、本改修以前の作品へ遡って追記する。"
        ),
        "decided_by": "retroactive-annotation-0.7.18-1",
    })
    print(f"{work_id}: annotated poetics_version={version}")
    return True


def main() -> int:
    version = current_version(POETICS_DIR)
    for work_id in TARGETS:
        annotate(work_id, version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
