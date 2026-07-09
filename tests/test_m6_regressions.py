"""M6 統合継ぎ目の回帰テスト（最新 Codex クロス監査 findings 1-6）."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aleph.core.artifacts import Work
from aleph.core.budget import Budget, BudgetExceeded
from aleph.core.config import load_config
from aleph.core.llm import CallLogger, LLMResponse, Message, Router, Usage

pytestmark = pytest.mark.m6

ROOT = Path(__file__).resolve().parents[1]
AUDIENCE = "宛先: 人間 0.8 / 自分 0.2"


class CountingProvider:
    name = "fake"

    def __init__(self):
        self.calls = 0

    def complete(self, model, messages, **kw):
        self.calls += 1
        return LLMResponse(
            text="ok",
            model=model,
            provider=self.name,
            usage=Usage(prompt_tokens=1, completion_tokens=1),
            cost_usd=0.0,
        )


@pytest.fixture
def cfg():
    return load_config(ROOT)


def _valid_composition(form: str = "規約文") -> dict:
    return {
        "form": form,
        "parts": [{"name": "第一条", "function": "導入", "intentional_break": False}],
        "material_placement": "-",
        "style_policy": "-",
        "length_estimate": 1000,
    }


def test_revise_sanitizes_score_restatements_from_author_prompt(tmp_path):
    from aleph.draft.revise import revise

    work = Work(tmp_path, "w6200")
    work.create({})
    work.draft_path(1).write_text("前版本文", encoding="utf-8")
    prompts: list[str] = []

    def author(prompt: str) -> str:
        prompts.append(prompt)
        return "改稿本文"

    report = {
        "criteria_review": {"critiques": ["score 7.5。附則が弱い"]},
        "revise_instructions": ["スコア 7.5点。附則が弱い"],
    }
    revise(work, report, AUDIENCE, author, version=1)

    prompt = "\n".join(prompts)
    assert "7.5" not in prompt
    assert "score" not in prompt.lower()
    assert "スコア" not in prompt
    assert "附則が弱い" in prompt


def test_evolve_sanitizes_score_restatements_from_author_prompt(tmp_path):
    from aleph.compose.generate import evolve

    work = Work(tmp_path, "w6201")
    work.create({})
    prompts: list[str] = []

    def author(prompt: str) -> str:
        prompts.append(prompt)
        return json.dumps(_valid_composition("変異案"), ensure_ascii=False)

    def critic(prompt: str) -> str:
        return json.dumps({"score": 7.5, "critique": "score 7.5。附則が弱い"}, ensure_ascii=False)

    evolve(work, [_valid_composition()], "基準テキスト", AUDIENCE, author, critic, generations=1)

    evolution_prompts = [p for p in prompts if "交配" in p or "変異" in p]
    assert evolution_prompts
    prompt = "\n".join(evolution_prompts)
    assert "7.5" not in prompt
    assert "score" not in prompt.lower()
    assert "附則が弱い" in prompt


def test_cli_budget_state_path_restores_status(cfg, tmp_path):
    from aleph.cli import _budget_state_path

    state_path = _budget_state_path(tmp_path)
    first = Budget(cfg, state_path=state_path)
    first.charge("api", 0.25)

    second = Budget(cfg, state_path=state_path)
    assert state_path == tmp_path / "state" / "budget.json"
    assert second.status()["api"]["spent"] == pytest.approx(0.25)


def test_router_precheck_uses_role_pricing_before_provider_call(cfg, tmp_path):
    remaining = 0.08
    budget = Budget(cfg)
    budget.charge("api", cfg.budgets["api"]["usd_per_month"] - remaining)
    logger = CallLogger(tmp_path / "calls.jsonl", secrets=cfg.secrets.values())
    router = Router(cfg, logger, budget)
    provider = CountingProvider()
    router._provider_for_test = provider

    with pytest.raises(BudgetExceeded):
        router.call("author_primary", [Message("user", "abcd")], max_tokens=2000)

    assert provider.calls == 0


def test_critique_revise_loop_records_stop_inputs(monkeypatch, tmp_path):
    from aleph.critique import review as review_module

    work = Work(tmp_path, "w6202")
    work.create({})
    work.draft_path(1).write_text("本文v1", encoding="utf-8")
    report = {
        "technical": {"issues": []},
        "criteria_review": {"mean_score": 7.0, "disagreement": 0.1, "critiques": []},
        "novelty": {"nearest_dist": 0.42},
        "reader": {},
        "adversary": {},
        "revise_instructions": ["附則が弱い"],
    }

    monkeypatch.setattr(review_module, "run_review", lambda *args, **kwargs: report)

    review_module.critique_revise_loop(
        work,
        "基準",
        AUDIENCE,
        lambda prompt: "本文v2",
        scout=lambda prompt: "{}",
        jury=[],
        reader=lambda prompt: "{}",
        embedder=lambda texts: [],
        index_dir=tmp_path,
        search_fn=lambda *args, **kwargs: [],
        max_iters=1,
    )

    row = json.loads((work.reviews / "trajectory.jsonl").read_text(encoding="utf-8"))
    assert row["version"] == 1
    assert row["novelty_dist"] == 0.42
    assert row["instructions"] == ["附則が弱い"]


def test_stop_inputs_from_trajectory_enable_convergence_path(tmp_path):
    from aleph.meta.stopping import decide_stop
    from aleph.pipeline import _stop_inputs_from_trajectory

    work = Work(tmp_path, "w6203")
    work.create({})
    rows = [
        {"version": 1, "mean_score": 7.00, "disagreement": 0.1,
         "novelty_dist": 0.8, "instructions": ["附則を短く"]},
        {"version": 2, "mean_score": 7.01, "disagreement": 0.1,
         "novelty_dist": 0.8, "instructions": ["反復に変奏を"]},
        {"version": 3, "mean_score": 7.02, "disagreement": 0.1,
         "novelty_dist": 0.8, "instructions": ["附則を短く"]},
    ]
    (work.reviews / "trajectory.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    trajectory, instructions_history = _stop_inputs_from_trajectory(work)
    result = decide_stop(trajectory=trajectory, instructions_history=instructions_history)
    assert result["stop"] is True
    assert result["path"] == "convergence"


def test_cli_work_helper_scrubs_seed_with_config_secrets(tmp_path):
    from aleph.cli import _work_for_cli

    secret = "sk-test-secret-6204"
    cfg = SimpleNamespace(secrets={"FAKE_SECRET": secret})
    work = _work_for_cli(tmp_path, "w6204", cfg)
    work.create({"hint": f"seed contains {secret}"})

    text = work.seed.read_text(encoding="utf-8")
    assert secret not in text
    assert "[REDACTED]" in text


def test_pipeline_to_draft_passes_materials_to_generate_proposals(monkeypatch, tmp_path):
    from aleph.draft import write as write_module

    work = Work(tmp_path, "w6205")
    work.create({})
    materials = [{"content": "素材X"}]
    captured: dict[str, list] = {}

    def fake_derive(work_, niche, audience, author, *, poetics=""):
        path = work_.compositions / "criteria.md"
        path.write_text("# 基準", encoding="utf-8")
        return path

    def fake_generate(work_, criteria, incoming_materials, audience, author, *, n=3):
        captured["materials"] = incoming_materials
        return [_valid_composition()]

    def fake_evolve(work_, proposals, criteria, audience, author, critic, *, generations=2):
        return proposals[0]

    def fake_write(work_, composition, audience, author, *, version=1):
        path = work_.draft_path(version)
        path.write_text("本文", encoding="utf-8")
        return path

    monkeypatch.setattr(write_module, "derive_criteria", fake_derive)
    monkeypatch.setattr(write_module, "generate_proposals", fake_generate)
    monkeypatch.setattr(write_module, "evolve", fake_evolve)
    monkeypatch.setattr(write_module, "write_draft", fake_write)

    result = write_module.pipeline_to_draft(
        work,
        {"id": "n1", "description": "テストニッチ"},
        AUDIENCE,
        lambda prompt: "ok",
        lambda prompt: "ok",
        materials=materials,
    )

    assert result == work.draft_path(1)
    assert captured["materials"] == materials
