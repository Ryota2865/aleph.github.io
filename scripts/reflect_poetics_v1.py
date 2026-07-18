"""詩学第1版リフレクションの一回性実行（PLAN_CHANGELOG 0.7.19-2 / 0.7.19-13）.

背景: w0008『暗い側』の FINISH 時、改訂周期は 3/3 に達したが
first_revision_requires_human_ack=false のため見送られ、周期カウントは消費済み。
2026-07-18 にオーナーが明示 ack（「宣言入力リフレクション(0.7.19-2)と初回ack
(0.7.19-13)は実施許可します」）を与えたため、登録どおり w0008 完成時点の入力で
reflect を一回だけ実行する。周期バイパスの理由は decisions.jsonl に記録する。

冪等: 現行詩学が第0版でない（既に改訂適用済み）の場合は何もせず終了する。
前提: ローカルスタック起動済み（adversary=reader ローカルモデル）、
      policies.poetics.first_revision_requires_human_ack=true。

実行: uv run python scripts/reflect_poetics_v1.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aleph.core.artifacts import Work  # noqa: E402
from aleph.core.budget import Budget  # noqa: E402
from aleph.core.config import load_config  # noqa: E402
from aleph.core.llm import CallLogger, Router  # noqa: E402
from aleph.meta.poetics import current_version  # noqa: E402
from aleph.pipeline import RealDeps  # noqa: E402

WORK_ID = "w0008"


def main() -> int:
    poetics_dir = ROOT / "poetics"
    version = current_version(poetics_dir)
    if version != 0:
        print(f"already revised: current poetics version = {version}; nothing to do", file=sys.stderr)
        return 0

    config = load_config(ROOT)
    ack = bool((config.policies.get("poetics") or {}).get("first_revision_requires_human_ack"))
    if not ack:
        print("first_revision_requires_human_ack is not true; refusing to run", file=sys.stderr)
        return 2

    work = Work(ROOT / "works", WORK_ID)
    logger = CallLogger(work.calls, secrets=config.secrets.values())
    budget = Budget(config, state_path=ROOT / "state" / "budget.json")
    deps = RealDeps(
        work,
        Router(config, logger, budget),
        config=config,
        index_dir=ROOT / "state" / "atlas",
        search_fn=lambda query, count=5: [],
        embedder=None,
        poetics_dir=poetics_dir,
    )

    work.append_decision({
        "ts": datetime.now(timezone.utc).isoformat(),
        "layer": "L8",
        "decision": "詩学第1版リフレクションを実行（オーナーack）",
        "reason": (
            "0.7.19-2/-13 の登録事項。w0008 FINISH 時に周期3/3へ達したが ack ゲート閉鎖で"
            "見送られ周期が消費されたため、オーナー明示 ack（2026-07-18「宣言入力リフレク"
            "ション(0.7.19-2)と初回ack(0.7.19-13)は実施許可します」）にもとづき周期を"
            "バイパスして一回だけ実行する。入力=w0008制作記録＋2024年の宣言。",
        ),
        "decided_by": "owner + orchestrator (Claude Code, Fable 5)",
        "refs": ["PLAN_CHANGELOG.md#0.7.19-2", "config/policies.yaml"],
    })

    result = deps.reflect_poetics(work, ignore_cadence=True)

    work.append_decision({
        "ts": datetime.now(timezone.utc).isoformat(),
        "layer": "L8",
        "decision": "詩学改訂を適用" if result.get("applied") else "詩学改訂は反駁され不適用",
        "reason": str(result.get("diff_reason", "")),
        "decided_by": "cli reflect_poetics_v1",
        "refs": ["poetics/poetics.md", "poetics/history.jsonl"],
    })

    print(f"applied={result.get('applied')} version_now={current_version(poetics_dir)}")
    print(f"diff_reason: {result.get('diff_reason', '')[:500]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
