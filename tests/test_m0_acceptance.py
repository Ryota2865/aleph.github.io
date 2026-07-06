"""M0 受入基準（PLAN §10 M0）— 施工対象。施工完了時に全て緑になること.

実行: pytest -m m0
監査者はこのファイルを照合表として使う（PLAN §12）。
テストを弱める変更（assertの削除・skip追加）は監査で不合格となる。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from aleph.core.artifacts import Work
from aleph.core.budget import Budget, BudgetExceeded
from aleph.core.config import load_config
from aleph.core.llm import CallLogger, LLMResponse, Message, Router, Usage
from aleph.core.loop import Checkpoint, State

pytestmark = pytest.mark.m0

ROOT = Path(__file__).resolve().parents[1]


class FakeProvider:
    """決定論的な偽プロバイダ。Routerのテスト用."""

    name = "fake"

    def __init__(self):
        self.calls = 0

    def complete(self, model, messages, **kw):
        self.calls += 1
        return LLMResponse(
            text=f"echo:{messages[-1].content}",
            model=model,
            provider=self.name,
            usage=Usage(prompt_tokens=10, completion_tokens=5),
            cost_usd=0.001,
        )


@pytest.fixture
def cfg():
    return load_config(ROOT)


# ---------------------------------------------------------------- 記録
def test_router_logs_every_call(cfg, tmp_path, monkeypatch):
    """不変条件: すべての呼び出しがcalls.jsonlに1行ずつ記録される（PLAN §2.1）."""
    log_path = tmp_path / "calls.jsonl"
    logger = CallLogger(log_path, secrets=cfg.secrets.values())
    budget = Budget(cfg)
    router = Router(cfg, logger, budget)
    monkeypatch.setattr(router, "_provider_for_test", FakeProvider(), raising=False)

    router.call("scout", [Message("user", "hello")])
    router.call("scout", [Message("user", "world")])

    lines = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    for rec in lines:
        for field in ("ts", "role", "provider", "model", "prompt_hash", "response_hash", "cost_usd"):
            assert field in rec, f"calls.jsonl 必須フィールド欠落: {field}"


def test_call_log_is_scrubbed(cfg, tmp_path):
    """秘密値がログに現れない（PLAN §14.2）."""
    secret = "sk-test-abcdef0123456789"
    logger = CallLogger(tmp_path / "calls.jsonl", secrets=[secret])
    logger.log({"ts": "2026-01-01T00:00:00Z", "note": f"leaky {secret} value"})
    assert secret not in (tmp_path / "calls.jsonl").read_text(encoding="utf-8")


# ---------------------------------------------------------------- 予算
def test_budget_exceeded_raises_before_call(cfg):
    """超過が予見される呼び出しは実行前に拒否される（PLAN §2.1）."""
    budget = Budget(cfg)
    limit = cfg.budgets["api"]["usd_per_month"]
    budget.charge("api", limit)  # 上限まで消費
    with pytest.raises(BudgetExceeded):
        budget.precheck("api", 0.01)


def test_budget_status_reports_three_ledgers(cfg):
    budget = Budget(cfg)
    status = budget.status()
    for ledger in ("api", "harness", "local"):
        assert ledger in status


# ---------------------------------------------------------------- 成果物と再開
def test_work_create_layout(tmp_path):
    work = Work(tmp_path, "w0001")
    work.create({"intent_hint": "test", "budget_usd": 1.0})
    assert work.seed.exists()
    assert work.drafts.is_dir()
    assert work.final.is_dir()


def test_decision_requires_author(tmp_path):
    """decisions.jsonl は decided_by 欠落を拒否する（PLAN §2.2）."""
    work = Work(tmp_path, "w0002")
    work.create({})
    with pytest.raises(Exception):
        work.append_decision({"ts": "2026-01-01T00:00:00Z", "decision": "x", "reason": "y"})


def test_checkpoint_resume(tmp_path):
    """クラッシュ後に任意の状態から再開できる（PLAN §2.4）."""
    work = Work(tmp_path, "w0003")
    work.create({})
    cp = Checkpoint(work_id="w0003", state=State.DRAFT, step=7, payload={"draft_version": 2})
    cp.save(work.dir)
    loaded = Checkpoint.load(work.dir)
    assert loaded.state == State.DRAFT
    assert loaded.step == 7
    assert loaded.payload["draft_version"] == 2


# ---------------------------------------------------------------- ローカル推論
@pytest.mark.local
@pytest.mark.skipif(os.environ.get("ALEPH_LOCAL") != "1", reason="要 RTX 3090 / llama-server (ALEPH_LOCAL=1)")
def test_local_swap(cfg):
    """gemma-4-26B-A4B の起動とswapを含めて動作する（PLAN §10 M0受入）."""
    from aleph.core.local import LocalRuntime

    rt = LocalRuntime(cfg)
    scout_model = cfg.models["roles"]["scout"]["model"]
    base_url = rt.ensure_model(scout_model)
    assert base_url.startswith("http")
    assert scout_model in rt.resident_models()
