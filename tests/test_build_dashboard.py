"""UI-1ダッシュボード(designs/ui.md)の集計ロジック契約.

読み取り専用（原則1: 既存の成果物だけを読み、新しい書き込み経路を作らない）ことを
純粋関数レベルで固定する。HTMLレンダリングそのものは目視確認の対象なので、ここでは
collect_*関数の集計結果を検証する。

実行: pytest -m m6 tests/test_build_dashboard.py
"""
from __future__ import annotations

import json
import os

import pytest

from scripts.build_dashboard import (
    collect_budget_status,
    collect_pending_gates,
    collect_recent_decisions,
    collect_works,
)

pytestmark = pytest.mark.m6


def _write_jsonl(path, records):
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )


def test_collect_works_reads_checkpoint_and_audience(tmp_path):
    wdir = tmp_path / "works" / "w0001"
    wdir.mkdir(parents=True)
    (wdir / "checkpoint.json").write_text(
        json.dumps({"work_id": "w0001", "state": "DRAFT", "step": 3, "payload": {}}),
        encoding="utf-8",
    )
    _write_jsonl(
        wdir / "decisions.jsonl",
        [
            {"ts": "2026-07-16T00:00:00+00:00", "layer": "L1", "decision": "志向配合比: LLM 1.0"},
            {"ts": "2026-07-16T01:00:00+00:00", "layer": "L0", "decision": "COMPOSE->DRAFT"},
        ],
    )
    works = collect_works(tmp_path)
    assert len(works) == 1
    w = works[0]
    assert w["id"] == "w0001"
    assert w["state"] == "DRAFT"
    assert w["step"] == 3
    assert w["audience"] == "志向配合比: LLM 1.0"
    assert w["last_ts"] == "2026-07-16T01:00:00+00:00"
    assert w["alive"] is None  # PIDファイルが無い


def test_collect_works_detects_dead_pid(tmp_path):
    wdir = tmp_path / "works" / "w0002"
    wdir.mkdir(parents=True)
    (wdir / "checkpoint.json").write_text(
        json.dumps({"work_id": "w0002", "state": "CRITIQUE", "step": 1, "payload": {}}),
        encoding="utf-8",
    )
    (wdir / "decisions.jsonl").write_text("", encoding="utf-8")
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    # 実在しない可能性が極めて高いPID(現行プロセスのPIDに大きな値を足す)
    (state_dir / "run_w0002.pid").write_text(str(os.getpid() + 987654), encoding="utf-8")
    works = collect_works(tmp_path)
    assert works[0]["alive"] is False


def test_collect_works_skips_dirs_without_checkpoint(tmp_path):
    wdir = tmp_path / "works" / "w0003"
    wdir.mkdir(parents=True)  # checkpoint.json なし(まだ走行していない/削除済み)
    assert collect_works(tmp_path) == []


def test_collect_budget_status_computes_publish_count_for_current_period(tmp_path):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "budget.json").write_text(
        json.dumps({"ledgers": {"api": {"spent": 10.0, "period_key": "2026-07"}}, "work_spent": {"w0001": 3.0}}),
        encoding="utf-8",
    )
    wdir = tmp_path / "works" / "w0001"
    wdir.mkdir(parents=True)
    _write_jsonl(
        wdir / "decisions.jsonl",
        [
            {"ts": "2026-07-12T00:00:00+00:00", "layer": "L0", "decision": "FINISH->PUBLISH"},
            {"ts": "2026-06-01T00:00:00+00:00", "layer": "L0", "decision": "FINISH->PUBLISH"},  # 期間外
        ],
    )
    budgets = {"api": {"usd_per_month": 52.0, "usd_per_work": 9.0}, "publish": {"max_per_month": 999}}
    status = collect_budget_status(tmp_path, budgets)
    assert status["api_spent"] == 10.0
    assert status["api_cap"] == 52.0
    assert status["publish_count"] == 1  # 今期のみカウント
    assert status["publish_cap"] == 999
    assert status["work_spent"] == {"w0001": 3.0}


def test_collect_pending_gates_flags_unacked_first_publish():
    budgets_status = {"api_cap": 52.0, "api_spent": 1.0}
    gates = collect_pending_gates(
        {"publication": {"first_publish_ack": False}, "poetics": {"first_revision_requires_human_ack": True}},
        budgets_status,
    )
    assert any("初回公開" in g for g in gates)
    assert not any("詩学" in g for g in gates)


def test_collect_pending_gates_flags_budget_over_80_percent():
    gates = collect_pending_gates(
        {"publication": {"first_publish_ack": True}, "poetics": {"first_revision_requires_human_ack": True}},
        {"api_cap": 50.0, "api_spent": 45.0},
    )
    assert any("80%" in g for g in gates)


def test_collect_pending_gates_empty_when_all_acked_and_under_budget():
    gates = collect_pending_gates(
        {"publication": {"first_publish_ack": True}, "poetics": {"first_revision_requires_human_ack": True}},
        {"api_cap": 50.0, "api_spent": 1.0},
    )
    assert gates == []


def test_collect_recent_decisions_merges_and_sorts_across_works(tmp_path):
    for wid, ts in (("w0001", "2026-07-16T00:00:00+00:00"), ("w0002", "2026-07-17T00:00:00+00:00")):
        wdir = tmp_path / "works" / wid
        wdir.mkdir(parents=True)
        _write_jsonl(wdir / "decisions.jsonl", [{"ts": ts, "layer": "L0", "decision": "x"}])
    merged = collect_recent_decisions(tmp_path, limit=10)
    assert [d["work_id"] for d in merged] == ["w0002", "w0001"]  # 新しい順


def test_collect_recent_decisions_respects_limit(tmp_path):
    wdir = tmp_path / "works" / "w0001"
    wdir.mkdir(parents=True)
    _write_jsonl(
        wdir / "decisions.jsonl",
        [{"ts": f"2026-07-{i:02d}T00:00:00+00:00", "layer": "L0", "decision": "x"} for i in range(1, 11)],
    )
    assert len(collect_recent_decisions(tmp_path, limit=3)) == 3
