"""M0 バグ修正の回帰テスト（Codexクロス監査 reports/CODEX_AUDIT_20260708_094819.md の指摘）.

設計不変条件・受入テスト本体（tests/test_m0_acceptance.py, tests/test_design_invariants.py）は
初代設計者の契約であり変更しない（PLAN §12）。ここでは施工者が発見した具体的なバグの
再発防止テストのみを追加する。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aleph.core.artifacts import Work
from aleph.core.budget import Budget, BudgetExceeded
from aleph.core.config import load_config
from aleph.core.llm import CallLogger, LLMResponse, Message, Router, Usage
from aleph.core.loop import Checkpoint, Loop, State

pytestmark = pytest.mark.m0

ROOT = Path(__file__).resolve().parents[1]


class FakeProvider:
    name = "fake"

    def complete(self, model, messages, **kw):
        return LLMResponse(
            text="ok",
            model=model,
            provider=self.name,
            usage=Usage(prompt_tokens=10, completion_tokens=5),
            cost_usd=0.001,
        )


@pytest.fixture
def cfg():
    return load_config(ROOT)


def test_router_blocks_call_that_would_exceed_harness_budget(cfg, tmp_path):
    """監査 finding 1: precheckがamount=0固定で、超過が予見される呼び出しを防げていなかった."""
    budget = Budget(cfg)
    limit = int(cfg.budgets["harness"]["calls_per_day"])
    budget.charge("harness", limit)  # 上限まで消費済みにする

    logger = CallLogger(tmp_path / "calls.jsonl", secrets=cfg.secrets.values())
    router = Router(cfg, logger, budget)
    router._provider_for_test = FakeProvider()

    with pytest.raises(BudgetExceeded):
        router.call("author_harness", [Message("user", "hello")])


def test_checkpoint_step_is_monotonic_across_resume(tmp_path):
    """監査 finding 3: 再開後に新しいLoopを作るとstepが1に巻き戻っていた."""
    work = Work(tmp_path, "w0004")
    work.create({})
    Checkpoint(work_id="w0004", state=State.DRAFT, step=7, payload={}).save(work.dir)

    loop = Loop(work, router=None, budget=None, policies=None)
    loop.transition(State.CRITIQUE, reason="resume-test", decided_by="test")

    resumed = Checkpoint.load(work.dir)
    assert resumed.step == 8


def test_budget_work_scoped_spend_survives_persistence(cfg, tmp_path):
    """監査 finding 4: 永続化時に作品別サブ台帳(_work_spent)が保存されていなかった."""
    state_path = tmp_path / "budget.json"
    work_limit = cfg.budgets["api"]["usd_per_work"]

    b1 = Budget(cfg, state_path=state_path)
    b1.charge("api", work_limit - 0.05, work_id="w0005")

    b2 = Budget(cfg, state_path=state_path)
    with pytest.raises(BudgetExceeded):
        b2.precheck("api", 0.10, work_id="w0005")


def test_router_propagates_work_id_to_budget(cfg, tmp_path):
    """2回目のCodex監査 finding: Router.callがwork_idをBudgetへ渡しておらず、
    作品別上限(usd_per_work)がRouter経由の呼び出しで一切機能していなかった."""
    budget = Budget(cfg)
    work_limit = cfg.budgets["api"]["usd_per_work"]
    budget.charge("api", work_limit, work_id="w0006")  # この作品の上限まで消費済み

    logger = CallLogger(tmp_path / "calls.jsonl", secrets=cfg.secrets.values())
    router = Router(cfg, logger, budget)
    router._provider_for_test = FakeProvider()

    with pytest.raises(BudgetExceeded):
        router.call("author_primary", [Message("user", "hello")], work_id="w0006")
