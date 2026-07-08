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
from aleph.core.llm import CallLogger, HarnessProvider, LLMResponse, Message, Router, Usage
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


def test_router_blocks_call_that_would_exceed_local_budget(cfg, tmp_path):
    """3回目のCodex監査 finding 1: local台帳が常にamount=0扱いで、上限到達済みでも
    router.call('scout', ...) がブロックされなかった（local台帳がRouter経由では
    事実上機能していなかった）."""
    budget = Budget(cfg)
    limit = cfg.budgets["local"]["gpu_hours_per_day"]
    budget.charge("local", limit)  # 上限まで消費済みにする

    logger = CallLogger(tmp_path / "calls.jsonl", secrets=cfg.secrets.values())
    router = Router(cfg, logger, budget)
    router._provider_for_test = FakeProvider()

    with pytest.raises(BudgetExceeded):
        router.call("scout", [Message("user", "hello")])


def test_harness_provider_does_not_leak_prompt_into_argv(monkeypatch):
    """3回目のCodex監査 finding 2: harnessの本文がコマンドライン引数(argv)に載り、
    同一ホストの他プロセスから `ps` 等で読める状態だった。本文はstdin経由に限定する."""
    captured = {}

    class FakeCompletedProcess:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(cmd, input=None, **kw):
        captured["cmd"] = cmd
        captured["input"] = input
        return FakeCompletedProcess()

    monkeypatch.setattr("aleph.core.llm.subprocess.run", fake_run)

    provider = HarnessProvider(cli="claude-code")
    secret_text = "SUPER-SECRET-DRAFT-CONTENT-0007"
    provider.complete("claude-code", [Message("user", secret_text)])

    assert secret_text not in captured["cmd"]
    assert secret_text in captured["input"]


def test_work_create_scrubs_secrets_from_seed(tmp_path):
    """4回目のCodex監査 finding: Work.create/append_decisionがscrub_secretsを
    経由しておらず、秘密値が成果物へ平文で書かれていた（seed.json）."""
    secret = "sk-test-secret-0123456789"
    work = Work(tmp_path, "w0008", secrets=[secret])
    work.create({"intent_hint": "test", "leaked": secret})
    assert secret not in work.seed.read_text(encoding="utf-8")


def test_work_append_decision_scrubs_secrets(tmp_path):
    """同上（decisions.jsonl）."""
    secret = "sk-test-secret-0123456789"
    work = Work(tmp_path, "w0009", secrets=[secret])
    work.create({})
    work.append_decision(
        {"ts": "2026-01-01T00:00:00Z", "decision": "x", "reason": f"leaky {secret}", "decided_by": "test"}
    )
    assert secret not in work.decisions.read_text(encoding="utf-8")
