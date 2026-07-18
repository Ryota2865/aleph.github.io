"""終端フックの回帰テスト（PLAN_CHANGELOG 0.7.18 問2・sol指摘の未接続機能の実配線）.

annotate_failure()（否定的地図）と poetics.reflect()（詩学自己改訂）は既に実装・
M1/M5契約テスト済みだったが、pipeline.py の実終端（FINISH→PUBLISH|SHELVE|DISCARD）
からは一度も呼ばれていなかった。本ファイルは (1) 4分類（aesthetic_failure等）の
振り分けロジック (2) deps未対応（M6契約のFakeDeps）でも壊れない後方互換性
(3) deps対応時に実際に呼ばれる配線、を固定する。

実行: pytest -m m6
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aleph.core.artifacts import Work
from aleph.core.loop import State
from aleph.core.transition_commit import initialize
from aleph.pipeline import _classify_termination, run_work

pytestmark = pytest.mark.m6


def _initialize_at_critique(work: Work, payload: dict) -> None:
    initialize(
        work,
        command_id="fixture:critique",
        state=State.CRITIQUE,
        reason="termination hook fixture",
        decided_by="test",
        payload=payload,
    )


# ---------------------------------------------------------------- 分類ロジック
def test_classify_termination_maps_budget_and_guard_to_resource_stop():
    assert _classify_termination("budget", "予算切れ") == "resource_stop"
    assert _classify_termination("guard_limit", "改稿上限に到達") == "resource_stop"


def test_classify_termination_maps_cap_and_ack_reasons_to_resource_stop():
    assert _classify_termination(None, "月間公開上限 4 作に到達しているため") == "resource_stop"
    assert _classify_termination(None, "初回公開は人間承認待ち") == "resource_stop"


def test_classify_termination_maps_author_declined_to_publication_choice():
    assert _classify_termination(None, "著者が非公開を選択した（自己宛ては非公開を意味しない）") \
        == "publication_choice"


def test_classify_termination_defaults_to_aesthetic_failure():
    assert _classify_termination(None, "品質の床を通過していないため、公開せず棚に戻す。") \
        == "aesthetic_failure"


# ---------------------------------------------------------------- 後方互換（FakeDeps）
class _MinimalDeps:
    """annotate_failure/reflect_poetics を持たない旧来のdeps（M6契約FakeDeps相当）."""

    def critique_and_revise(self, work, audience):
        return 2

    def decide_stop(self, work):
        return {"stop": True, "path": "budget", "reason": "予算切れ"}

    def decide_publication(self, work, audience):
        return {"decision": "SHELVE", "reason": "品質の床を通過していないため"}


def test_run_work_without_hook_methods_still_shelves(tmp_path):
    """annotate_failure/reflect_poetics未対応のdepsでも例外なく終端する（後方互換）."""
    work = Work(tmp_path / "works", "w9101")
    work.create({})
    _initialize_at_critique(work, {"audience": "自分 1.0"})

    final = run_work(work, _MinimalDeps(), decided_by="hook-test")
    assert final == State.SHELVE


# ---------------------------------------------------------------- 実配線
class _HookedDeps(_MinimalDeps):
    """annotate_failure/reflect_poeticsを実装し、呼び出しを記録するdeps."""

    def __init__(self, publish_decision="SHELVE", stop_reason="品質の床を通過していないため",
                 stop_path="convergence"):
        self.publish_decision = publish_decision
        self.stop_reason = stop_reason
        self.stop_path = stop_path
        self.annotate_calls: list[tuple] = []
        self.reflect_calls = 0

    def decide_stop(self, work):
        return {"stop": True, "path": self.stop_path, "reason": "テスト擱筆"}

    def decide_publication(self, work, audience):
        return {"decision": self.publish_decision, "reason": self.stop_reason}

    def annotate_failure(self, work, niche_desc, reason):
        self.annotate_calls.append((niche_desc, reason))

    def reflect_poetics(self, work):
        self.reflect_calls += 1
        return {"applied": True, "diff_reason": "テスト改訂"}


def test_aesthetic_failure_is_recorded_and_annotated(tmp_path):
    """品質床未達によるSHELVEはaesthetic_failureに分類され、否定的地図へ渡される."""
    work = Work(tmp_path / "works", "w9102")
    work.create({})
    _initialize_at_critique(
        work,
        {"audience": "自分 1.0", "niche": {"description": "空虚な断片"}},
    )
    deps = _HookedDeps(stop_reason="品質の床を通過していないため、公開せず棚に戻す。")

    final = run_work(work, deps, decided_by="hook-test")
    assert final == State.SHELVE
    assert deps.annotate_calls == [("空虚な断片", "品質の床を通過していないため、公開せず棚に戻す。")]
    assert deps.reflect_calls == 1

    decisions = [json.loads(l) for l in work.decisions.read_text(encoding="utf-8").splitlines()]
    failure_records = [d for d in decisions if d["decision"].startswith("failure_category:")]
    assert failure_records[-1]["decision"] == "failure_category:aesthetic_failure"


def test_resource_stop_is_recorded_but_not_annotated(tmp_path):
    """予算切れによるSHELVEはresource_stopに分類され、否定的地図へは渡されない
    （sol提案: 探索座標を罰しない）."""
    work = Work(tmp_path / "works", "w9103")
    work.create({})
    _initialize_at_critique(
        work,
        {"audience": "自分 1.0", "niche": {"description": "有望な空隙"}},
    )
    deps = _HookedDeps(stop_reason="予算・時間の残量が尽きたため強制的に擱筆する。", stop_path="budget")

    final = run_work(work, deps, decided_by="hook-test")
    assert final == State.SHELVE
    assert deps.annotate_calls == [], "resource_stopは否定的地図へ渡してはならない"
    assert deps.reflect_calls == 1

    decisions = [json.loads(l) for l in work.decisions.read_text(encoding="utf-8").splitlines()]
    failure_records = [d for d in decisions if d["decision"].startswith("failure_category:")]
    assert failure_records[-1]["decision"] == "failure_category:resource_stop"


def test_reflect_poetics_runs_on_publish_too(tmp_path):
    """PUBLISHでも詩学リフレクションは呼ばれる（PLAN §7.4「完成後」）."""
    work = Work(tmp_path / "works", "w9104")
    work.create({})
    _initialize_at_critique(work, {"audience": "人間 1.0"})
    work.draft_path(1).write_text("本文v1。" * 50, encoding="utf-8")
    deps = _HookedDeps(publish_decision="PUBLISH", stop_reason="公開に値する")

    final = run_work(work, deps, decided_by="hook-test")
    assert final == State.PUBLISH
    assert deps.reflect_calls == 1
