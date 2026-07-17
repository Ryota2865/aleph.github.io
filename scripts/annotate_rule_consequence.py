"""w0001-w0003への rule_consequence 遡及注釈（Fable 5審査、PLAN_CHANGELOG 0.7.18-1 問2）.

w0001-w0003 は 0.7.15（宛先「自分」と公開判断の分離）以前の旧契約下で、
「自分」最大の宛先配合を理由に自動SHELVEされた。これは publication_choice
（著者が非公開を選択）でも aesthetic_failure（品質の問題）でもない——著者に
選択の機会がないまま規則によって棚入りした、という第五の履歴。

既存の decisions.jsonl 行は一切書き換えず、再分類イベントを追記するのみ。
否定的地図（annotate_failure）へは渡さない——rule_consequence はニッチの
文学的失敗を意味しないため、探索座標を罰してはならない。

一回限りの実行用（冪等: 既に注釈済みの作品はスキップ）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from aleph.core.artifacts import Work

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("w0001", "w0002", "w0003")


def _already_annotated(work: Work) -> bool:
    if not work.decisions.exists():
        return False
    text = work.decisions.read_text(encoding="utf-8")
    return "failure_category:rule_consequence" in text


def annotate(work_id: str) -> bool:
    work = Work(ROOT / "works", work_id)
    if _already_annotated(work):
        print(f"{work_id}: already annotated, skip")
        return False
    work.append_decision({
        "ts": datetime.now(timezone.utc).isoformat(),
        "layer": "L7",
        "decision": "failure_category:rule_consequence",
        "reason": (
            "遡及注釈（PLAN_CHANGELOG 0.7.18-1、Fable 5審査 問2）。本作は0.7.15"
            "（宛先「自分」と公開判断の分離）以前の旧契約下で、宛先配合『自分』最大を"
            "理由に自動SHELVEされた。著者が非公開を選択した(publication_choice)のでも、"
            "品質の床を割った(aesthetic_failure)のでもなく、規則の帰結として棚入りした。"
            "否定的地図へは渡さない（探索座標を罰しない）。既存のdecisions.jsonl行は"
            "書き換えず、本イベントを追記するのみ。"
        ),
        "decided_by": "retroactive-annotation-0.7.18-1",
    })
    print(f"{work_id}: annotated")
    return True


def main() -> int:
    for work_id in TARGETS:
        annotate(work_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
