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
    # 境界は author_primary の宣言価格から動的に計算する(著者モデルの切替に依存しない)
    out_per_mtok = cfg.models["roles"]["author_primary"]["pricing"]["output_per_mtok"]
    estimate = 2000 * out_per_mtok / 1e6
    remaining = estimate * 0.8
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


def test_find_hidden_pairs_min_chars_excludes_heading_only_chunks(tmp_path):
    """章番号だけのチャンク(「一」等)は min_chars 指定で候補から除外される.

    w0001 実ランで素材カード5枚全てが「一」「二」の対に縮退した回帰
    (埋め込みほぼ同一×表層は空白差のみ → score 上位を自明対が占有)。
    """
    import numpy as np

    from aleph.materia.similarity import find_hidden_pairs

    dim = 8
    base = np.zeros(dim); base[0] = 1.0
    other = np.zeros(dim); other[1] = 1.0
    long_a = (
        "エントロピーは不可逆過程において増大するという法則を、彼は恋愛の終わりに"
        "重ねて考えていた。戻らない方向にだけ進む時間の矢が、部屋の湿度にまで染みて、"
        "窓の外の夕暮れを少しずつ取り返しのつかない色に変えていくのだった。"
    )
    long_b = (
        "あの日から、心は戻らない方向へだけ動いた。物理学の講義で聞いた言葉が、"
        "なぜか毎晩、消灯後の天井に浮かんでは消える。誰にも言えない計算だった。"
        "式の両辺に残るのは、いつも取り返しのつかなさだけだった。"
    )
    rows = [
        {"chunk_id": "j1", "work_id": "w1", "title": "甲", "author": "A",
         "seq": 0, "text": "一", "char_len": 1, "meta": {"era": "1920"}},
        {"chunk_id": "j2", "work_id": "w2", "title": "乙", "author": "B",
         "seq": 0, "text": "　　　　一", "char_len": 5, "meta": {"era": "1950"}},
        {"chunk_id": "s1", "work_id": "w3", "title": "丙", "author": "C",
         "seq": 0, "text": long_a, "char_len": len(long_a), "meta": {"era": "1950"}},
        {"chunk_id": "s2", "work_id": "w4", "title": "丁", "author": "D",
         "seq": 0, "text": long_b, "char_len": len(long_b), "meta": {"era": "1890"}},
    ]
    vecs = np.stack([base, base * 0.999, other, other * 0.98]).astype(np.float32)
    np.save(tmp_path / "embeddings.npy", vecs)
    with (tmp_path / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (tmp_path / "manifest.json").write_text(
        json.dumps({"n_works": 4, "n_chunks": 4, "dim": dim}), encoding="utf-8",
    )

    pairs = find_hidden_pairs(tmp_path, top_n=10, min_chars=80)
    ids = [{p["chunk_a"], p["chunk_b"]} for p in pairs]
    assert {"j1", "j2"} not in ids, "見出しだけの自明対が min_chars で除外されていない"
    assert {"s1", "s2"} in ids, "実質のある対が失われている"

    # 既定値(min_chars=0)では従来挙動(junkも候補に載る)= 既存テスト互換
    pairs_default = find_hidden_pairs(tmp_path, top_n=10)
    ids_default = [{p["chunk_a"], p["chunk_b"]} for p in pairs_default]
    assert {"j1", "j2"} in ids_default


def test_generate_proposals_raises_loudly_when_all_attempts_unparseable(tmp_path):
    """全試行でJSON抽出に失敗したら、空リストを黙って返さずラウドに失敗する.

    w0001 実ランの回帰: 空の proposals が evolve まで素通りし
    scored[0] の IndexError でクラッシュした。診断用に最終応答も保存する。
    """
    from aleph.compose.generate import generate_proposals

    work = Work(tmp_path, "w6203")
    author = lambda prompt: "構成案をうまく書けませんでした。JSONはありません。"  # noqa: E731

    with pytest.raises(RuntimeError, match="有効な構成案が0件"):
        generate_proposals(work, "基準", [], AUDIENCE, author, n=3)
    failure = work.compositions / "proposal_parse_failure.txt"
    assert failure.exists() and "JSONはありません" in failure.read_text(encoding="utf-8")


def test_evolve_rejects_empty_candidates(tmp_path):
    """evolve は空の候補リストを明示的に拒否する(IndexErrorではなくValueError)."""
    from aleph.compose.generate import evolve

    work = Work(tmp_path, "w6204")
    with pytest.raises(ValueError, match="候補が0件"):
        evolve(work, [], "基準", AUDIENCE, lambda p: "ok", lambda p: "ok")


def test_budget_work_remaining_accessor(cfg, tmp_path):
    """Budget.work_remaining は作品別上限の残額を返す(未宣言なら None)."""
    budget = Budget(cfg, state_path=tmp_path / "budget.json")
    limit = cfg.budgets["api"]["usd_per_work"]
    budget.charge("api", 1.5, work_id="wX")
    assert budget.work_remaining("wX") == pytest.approx(limit - 1.5)
    assert budget.work_remaining("unseen") == pytest.approx(limit)


def test_decide_stop_regression_path_on_score_drop():
    """改稿でスコアが有意に下落したら擱筆する(w0002実ラン 8.80→8.33 の回帰)."""
    from aleph.meta.stopping import decide_stop

    result = decide_stop(
        trajectory=[{"mean_score": 8.8}, {"mean_score": 8.33}],
        instructions_history=[["a"], ["b"]],
        k=3, epsilon=0.05,
    )
    assert result["stop"] is True and result["path"] == "regression"


def test_remaining_api_budget_uses_min_of_work_and_month(cfg, tmp_path):
    """予算経路は作品残額と月残額の小さい方を見る(月上限precheckクラッシュの回帰)."""
    from aleph.pipeline import _remaining_api_budget

    budget = Budget(cfg, state_path=tmp_path / "budget.json")
    month_limit = cfg.budgets["api"]["usd_per_month"]
    work_limit = cfg.budgets["api"]["usd_per_work"]
    # 別作品で月枠を大きく消費 → 対象作品の残額は月残額で頭打ちになる
    budget.charge("api", month_limit - 1.0, work_id="other")
    remaining = _remaining_api_budget(budget, "wY")
    assert remaining == pytest.approx(min(1.0, work_limit))


def test_run_work_resume_skips_duplicate_critique_when_trajectory_full(tmp_path):
    """CRITIQUE再開時、査読軌跡が2ラウンド分あれば擱筆判定を先に行い重複査読しない.

    w0001 実ランの回帰: 予算切れクラッシュからの再開が査読一式(API実費+ローカル
    数十分)を再実行してしまう。
    """
    from aleph.core.loop import State
    from aleph.core.transition_commit import initialize
    from aleph.pipeline import run_work

    work = Work(tmp_path / "works", "w6206")
    work.create({})
    reviews = work.dir / "reviews"
    reviews.mkdir(exist_ok=True)
    rows = [
        {"version": 1, "mean_score": 8.6, "instructions": ["a"]},
        {"version": 2, "mean_score": 8.57, "instructions": ["b"]},
    ]
    (reviews / "trajectory.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8",
    )
    initialize(
        work,
        command_id="fixture:critique",
        state=State.CRITIQUE,
        reason="resume regression fixture",
        decided_by="test",
        payload={"audience": "自分 1.0"},
    )

    calls: list[str] = []

    class Deps:
        def critique_and_revise(self, work_, audience):
            calls.append("critique")
            return 2

        def decide_stop(self, work_):
            calls.append("stop")
            return {"stop": True, "path": "budget", "reason": "残額が改稿1サイクル未満"}

        def decide_publication(self, work_, audience):
            calls.append("gate")
            return {"decision": "SHELVE", "reason": "テスト"}

    final = run_work(work, Deps(), decided_by="regression-test")
    assert final == State.SHELVE
    assert "critique" not in calls, "軌跡が揃っているのに査読を重複実行した"
    assert calls[0] == "stop"


def test_pipeline_to_draft_reuses_compose_artifacts_on_resume(monkeypatch, tmp_path):
    """COMPOSE成果物(criteria/proposals/winner)が既にあれば author を再呼び出ししない.

    w0001 実ランの回帰: COMPOSE 途中クラッシュからの再開が criteria+proposals を
    毎回作り直し、author 実費(~$1.5)を再支出していた。
    """
    import aleph.draft.write as write_module

    work = Work(tmp_path, "w6205")
    work.compositions.mkdir(parents=True, exist_ok=True)
    work.draft_path(1).parent.mkdir(parents=True, exist_ok=True)
    (work.compositions / "criteria.md").write_text("既存の基準", encoding="utf-8")
    proposal = {
        "form": "短編", "parts": ["起", "結"], "material_placement": "冒頭",
        "style_policy": "簡素", "length_estimate": "4000字",
    }
    for i in (1, 2, 3):
        (work.compositions / f"proposal_{i}.json").write_text(
            json.dumps(proposal, ensure_ascii=False), encoding="utf-8",
        )
    (work.compositions / "winner.json").write_text(
        json.dumps(proposal, ensure_ascii=False), encoding="utf-8",
    )

    def must_not_call(*args, **kwargs):
        raise AssertionError("成果物があるのに高価な段階が再実行された")

    monkeypatch.setattr(write_module, "derive_criteria", must_not_call)
    monkeypatch.setattr(write_module, "generate_proposals", must_not_call)
    monkeypatch.setattr(write_module, "evolve", must_not_call)

    def fake_write(work_, composition, audience, author, *, version=1):
        assert composition == proposal
        path = work_.draft_path(version)
        path.write_text("本文", encoding="utf-8")
        return path

    monkeypatch.setattr(write_module, "write_draft", fake_write)

    result = write_module.pipeline_to_draft(
        work, {"id": "n1", "description": "ニッチ"}, AUDIENCE,
        must_not_call, must_not_call,
    )
    assert result == work.draft_path(1)
