from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import numpy as np
import pytest

from aleph.core.artifacts import Work
from aleph.core.llm import AnthropicProvider, Message, OpenAICompatProvider

pytestmark = pytest.mark.m6

AUDIENCE = "宛先: 人間 0.8 / 自分 0.2"


def _write_index(tmp_path: Path, rows: list[dict], vectors: np.ndarray) -> Path:
    index = tmp_path / "index"
    index.mkdir()
    np.save(index / "embeddings.npy", vectors.astype(np.float32))
    with (index / "chunks.jsonl").open("w", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False) + "\n")
    return index


def _row(chunk_id: str, work_id: str, title: str, author: str, text: str, era: str) -> dict:
    return {
        "chunk_id": chunk_id,
        "work_id": work_id,
        "title": title,
        "author": author,
        "seq": 0,
        "text": text,
        "char_len": len(text),
        "meta": {"era": era},
    }


def _pair_ids(pairs: list[dict]) -> list[set[str]]:
    return [{pair["chunk_a"], pair["chunk_b"]} for pair in pairs]


def test_find_hidden_pairs_focus_vec_and_exclude_pairs_preserve_defaults(tmp_path):
    from aleph.materia.similarity import find_hidden_pairs

    a = np.zeros(4)
    a[0] = 1.0
    b = np.zeros(4)
    b[1] = 1.0
    rows = [
        _row("a1", "w1", "甲", "A", "熱の不可逆性が記憶の戻れなさに重なる。" * 4, "1900"),
        _row("a2", "w2", "乙", "B", "心は一方向にだけ進み、帰路を失っていく。" * 4, "1950"),
        _row("b1", "w3", "丙", "C", "都市の沈黙が規約の空白として立ち上がる。" * 4, "1880"),
        _row("b2", "w4", "丁", "D", "規約の余白にだけ、都市の沈黙が記録される。" * 4, "1960"),
    ]
    index = _write_index(tmp_path, rows, np.stack([a, a * 0.99, b, b * 0.99]))

    default_pairs = find_hidden_pairs(index, top_n=10, knn_k=3)
    explicit_default_pairs = find_hidden_pairs(
        index, top_n=10, knn_k=3, focus_vec=None, exclude_pairs=None
    )
    assert explicit_default_pairs == default_pairs

    focused = find_hidden_pairs(index, top_n=10, knn_k=3, focus_vec=b, focus_top_m=2)
    assert _pair_ids(focused) == [{"b1", "b2"}]

    excluded = find_hidden_pairs(
        index,
        top_n=10,
        knn_k=3,
        exclude_pairs={tuple(sorted(("b1", "b2")))},
    )
    assert {"b1", "b2"} not in _pair_ids(excluded)


def test_find_hidden_pairs_focus_vec_restricts_before_knn(tmp_path):
    from aleph.materia.similarity import find_hidden_pairs

    def angled(degrees: float) -> np.ndarray:
        radians = np.deg2rad(degrees)
        return np.array([np.cos(radians), np.sin(radians)], dtype=np.float64)

    rows = [
        _row("f1", "w1", "甲", "A", "焦点近傍にある第一の実質本文。" * 4, "1900"),
        _row("f2", "w2", "乙", "B", "焦点近傍にある第二の実質本文。" * 4, "1950"),
        _row("d1", "w3", "丙", "C", "焦点外だが第一本文の近くに密集する文章。" * 4, "1880"),
        _row("d2", "w4", "丁", "D", "焦点外だが第二本文の近くに密集する文章。" * 4, "1960"),
        _row("d3", "w5", "戊", "E", "焦点外の追加ダミー本文。" * 4, "1970"),
        _row("d4", "w6", "己", "F", "焦点外の別の追加ダミー本文。" * 4, "1980"),
    ]
    vectors = np.stack([
        angled(20.0),
        angled(-20.0),
        angled(21.0),
        angled(-21.0),
        angled(22.0),
        angled(-22.0),
    ])
    index = _write_index(tmp_path, rows, vectors)

    pairs = find_hidden_pairs(
        index,
        top_n=10,
        knn_k=1,
        focus_vec=np.array([1.0, 0.0]),
        focus_top_m=2,
        min_chars=20,
    )

    assert _pair_ids(pairs) == [{"f1", "f2"}]


class _SparseAtlas:
    index_dir = None
    meta = {"clusters": []}
    chunks = [
        {"chunk_id": "c1", "text": "疎領域一"},
        {"chunk_id": "c2", "text": "疎領域二"},
        {"chunk_id": "c3", "text": "疎領域三"},
    ]

    def sparse_regions(self, top_n: int) -> list[dict]:
        return [
            {"chunk_id": "c1", "work_id": "w1", "title": "一", "knn_dist": 0.9, "nearest_cluster": -1},
            {"chunk_id": "c2", "work_id": "w2", "title": "二", "knn_dist": 0.2, "nearest_cluster": -1},
            {"chunk_id": "c3", "work_id": "w3", "title": "三", "knn_dist": 0.6, "nearest_cluster": -1},
        ][:top_n]


def test_find_niches_measured_novelty_varies_when_scout_scores_saturate():
    from aleph.explore.niche import find_niches

    def saturated_scout(prompt: str) -> str:
        if "どんな作品の空隙" in prompt:
            return json.dumps({"description": "飽和した候補", "novelty": 1.0}, ensure_ascii=False)
        return json.dumps(
            {
                "vacancy_type": "未着手型",
                "depth": "高",
                "rationale": "scout値は飽和",
                "interpretability": 0.8,
                "novelty": 1.0,
            },
            ensure_ascii=False,
        )

    niches = find_niches(_SparseAtlas(), saturated_scout, top_n=3)
    measured = [niche.get("measured_novelty") for niche in niches]

    assert len(niches) == 3
    assert len({value for value in measured if value is not None}) > 1


def test_real_deps_explore_passes_web_checker_when_secret_exists(monkeypatch, tmp_path):
    from aleph import pipeline as pipeline_module
    from aleph.explore import atlas as atlas_module
    from aleph.explore import niche as niche_module
    from aleph.explore import webresearch as web_module

    work = Work(tmp_path / "works", "w7001")
    work.create({})
    captured: dict = {}

    def fake_find_niches(atlas, scout, *, top_n, web_checker=None):
        captured["web_checker"] = web_checker
        captured["web_result"] = web_checker({"description": "照合候補"}) if web_checker else None
        return [{"id": "n1", "description": "照合候補"}]

    def fake_web_check(niche, search_fn, scout):
        captured["search_fn"] = search_fn
        captured["niche"] = niche
        return {"excluded": False}

    def fake_search(*args, **kwargs):
        return []

    monkeypatch.setattr(atlas_module, "build_atlas", lambda index_dir: object())
    monkeypatch.setattr(niche_module, "find_niches", fake_find_niches)
    monkeypatch.setattr(niche_module, "report", lambda niches, out_path, top_n=20: None)
    monkeypatch.setattr(web_module, "web_check", fake_web_check)

    deps = pipeline_module.RealDeps(
        work,
        router=SimpleNamespace(),
        config=SimpleNamespace(secrets={"BRAVE_API_KEY": "present"}),
        index_dir=tmp_path / "index",
        search_fn=fake_search,
    )
    result = deps.explore(work)

    assert result["id"] == "n1"
    assert callable(captured["web_checker"])
    assert captured["search_fn"] is fake_search
    assert captured["niche"]["description"] == "照合候補"


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(("stop_reason", "expected"), [("max_tokens", True), ("end_turn", False)])
def test_anthropic_provider_sets_truncated_from_stop_reason(stop_reason, expected):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
                "stop_reason": stop_reason,
            },
        )

    provider = AnthropicProvider(api_key="test-key", client=_client(handler))
    response = provider.complete("m", [Message("user", "hi")])

    assert response.truncated is expected


@pytest.mark.parametrize(("finish_reason", "expected"), [("length", True), ("stop", False)])
def test_openai_compat_provider_sets_truncated_from_finish_reason(finish_reason, expected):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": finish_reason}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    provider = OpenAICompatProvider(base_url="http://test/v1", api_key="k", name="fake", client=_client(handler))
    response = provider.complete("m", [Message("user", "hi")])

    assert response.truncated is expected


def test_revise_falls_back_to_targeted_sections_when_full_rewrite_is_too_short(tmp_path):
    from aleph.draft.revise import revise

    work = Work(tmp_path, "w7002")
    work.create({})
    section1 = "## 第一節\n" + "導入を保つ。" * 80 + "\n"
    section2 = "## 第二節\n" + "宣言はまだ弱い。" * 80 + "\n"
    section3 = "## 第三節\n" + "結尾を保つ。" * 80 + "\n"
    previous = section1 + section2 + section3
    work.draft_path(1).write_text(previous, encoding="utf-8")
    prompts: list[str] = []

    def author(prompt: str) -> str:
        prompts.append(prompt)
        if len(prompts) == 1:
            return "短い"
        return "## 第二節\n" + "宣言を強めた文章。" * 90 + "\n"

    report = {
        "criteria_review": {"critiques": ["宣言を強める"]},
        "revise_instructions": ["終盤の宣言を強める"],
    }
    path = revise(work, report, AUDIENCE, author, version=1)
    revised = path.read_text(encoding="utf-8")

    assert len(prompts) == 2
    assert len(revised) >= len(previous) * 0.8
    assert "短い" not in revised
    assert section1 in revised
    assert section3 in revised
    assert "宣言を強めた文章" in revised
    assert all("score" not in prompt.lower() and "スコア" not in prompt for prompt in prompts)


def test_critique_revise_loop_records_best_version_decision(monkeypatch, tmp_path):
    from aleph.critique import review as review_module

    work = Work(tmp_path, "w7003")
    work.create({})
    work.draft_path(1).write_text("本文v1", encoding="utf-8")
    scores = {1: 4.0, 2: 8.5}

    def fake_run_review(*args, version: int, **kwargs):
        return {
            "criteria_review": {
                "mean_score": scores[version],
                "disagreement": 0.1,
                "critiques": [],
            },
            "novelty": {"nearest_dist": 0.3},
            "revise_instructions": [],
        }

    monkeypatch.setattr(review_module, "run_review", fake_run_review)

    final_version = review_module.critique_revise_loop(
        work,
        "基準",
        AUDIENCE,
        lambda prompt: "本文v2" if "本文v1" in prompt else "本文v3",
        scout=lambda prompt: "{}",
        jury=[],
        reader=lambda prompt: "{}",
        embedder=lambda texts: [],
        index_dir=tmp_path,
        search_fn=lambda *args, **kwargs: [],
        max_iters=2,
    )

    decisions = [json.loads(line) for line in work.decisions.read_text(encoding="utf-8").splitlines()]
    assert isinstance(final_version, int)
    assert final_version == 3
    assert any(
        decision.get("decision") == "採用 v2"
        and decision.get("best_version") == 2
        and decision.get("decided_by") == "critique_revise_loop"
        for decision in decisions
    )


def test_finalize_publish_uses_highest_mean_score_draft(tmp_path):
    from aleph.pipeline import _finalize_publish

    work = Work(tmp_path, "w7004")
    work.create({"title": "公開本文選抜"})
    work.draft_path(1).write_text("本文v1", encoding="utf-8")
    work.draft_path(2).write_text("本文v2", encoding="utf-8")
    work.draft_path(3).write_text("本文v3", encoding="utf-8")
    rows = [
        {"version": 1, "mean_score": 7.0, "disagreement": 0.2},
        {"version": 2, "mean_score": 8.5, "disagreement": 0.1},
        {"version": 3, "mean_score": 6.0, "disagreement": 0.3},
    ]
    (work.reviews / "trajectory.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    _finalize_publish(work, SimpleNamespace())

    assert (work.final / "text.md").read_text(encoding="utf-8") == "本文v2"


def test_finalize_publish_falls_back_to_latest_without_trajectory(tmp_path):
    from aleph.pipeline import _finalize_publish

    work = Work(tmp_path, "w7005")
    work.create({"title": "公開本文選抜"})
    work.draft_path(1).write_text("本文v1", encoding="utf-8")
    work.draft_path(2).write_text("本文v2", encoding="utf-8")
    work.draft_path(3).write_text("本文v3", encoding="utf-8")

    _finalize_publish(work, SimpleNamespace())

    assert (work.final / "text.md").read_text(encoding="utf-8") == "本文v3"


# ============================================================ 実験D 配線（0.7.14）
LLM_AUDIENCE = "LLM 0.6 / 自分 0.25 / 人間 0.15"
HUMAN_AUDIENCE = "人間 0.8 / 自分 0.2"


def test_force_audience_skips_choose_intent_and_records_owner_experiment(monkeypatch, tmp_path):
    """--force-audience 指定時、L1 は choose_intent を呼ばず owner-experiment を記録する."""
    from aleph.intent import choose as choose_module
    from aleph.pipeline import RealDeps

    def boom(*args, **kwargs):
        raise AssertionError("choose_intent が強制宛先時に呼ばれた")

    monkeypatch.setattr(choose_module, "choose_intent", boom)

    work = Work(tmp_path / "works", "w7101")
    work.create({})
    deps = RealDeps(
        work, router=SimpleNamespace(), config=SimpleNamespace(secrets={}, policies={}),
        index_dir=tmp_path / "idx", search_fn=lambda *a, **k: [],
        force_audience=LLM_AUDIENCE,
    )
    audience = deps.choose_intent(work)
    assert audience == LLM_AUDIENCE
    decisions = [json.loads(l) for l in work.decisions.read_text(encoding="utf-8").splitlines()]
    l1 = [d for d in decisions if d["layer"] == "L1"]
    assert l1 and l1[-1]["decided_by"] == "owner-experiment"
    assert LLM_AUDIENCE in l1[-1]["decision"]


def _real_deps_for_materials(tmp_path, audience: str):
    from aleph.core.loop import Checkpoint, State
    from aleph.pipeline import RealDeps

    work = Work(tmp_path / "works", "w7102")
    work.create({})
    Checkpoint(work_id="w7102", state=State.MATERIA, step=3,
               payload={"audience": audience}).save(work.dir)
    deps = RealDeps(
        work, router=SimpleNamespace(), config=SimpleNamespace(secrets={}, policies={}),
        index_dir=tmp_path / "no_index", search_fn=lambda *a, **k: [], embedder=None,
    )
    return work, deps


def test_gather_materials_adds_anti_cliche_card_only_for_llm_audience(monkeypatch, tmp_path):
    """宛先がLLM最大のとき anti_cliche 素材が混ざる。人間最大では混ざらない（§5.4）."""
    from aleph.materia import ai_native

    fake_card = {"content": "意外な一文", "method": "anti_cliche", "tags": ["ai_native"]}
    monkeypatch.setattr(ai_native, "anti_cliche", lambda *a, **k: dict(fake_card))

    work_llm, deps_llm = _real_deps_for_materials(tmp_path / "a", LLM_AUDIENCE)
    cards = deps_llm.gather_materials(work_llm, {"id": "n1", "description": "鉱山の音響"})
    assert any(c.get("method") == "anti_cliche" for c in cards)

    def boom(*args, **kwargs):
        raise AssertionError("人間宛で anti_cliche が呼ばれた")

    monkeypatch.setattr(ai_native, "anti_cliche", boom)
    work_h, deps_h = _real_deps_for_materials(tmp_path / "b", HUMAN_AUDIENCE)
    cards_h = deps_h.gather_materials(work_h, {"id": "n1", "description": "鉱山の音響"})
    assert not any(c.get("method") == "anti_cliche" for c in cards_h)


def test_derive_criteria_injects_ai_native_only_for_llm_audience(tmp_path):
    """LLM最大の宛先でのみ §5.4 技法が criteria プロンプトへ注入される."""
    from aleph.compose.generate import derive_criteria

    niche = {"description": "テストニッチ"}

    prompts: list[str] = []
    derive_criteria(Work(tmp_path / "wl", "w7103"), niche, LLM_AUDIENCE,
                    lambda p: (prompts.append(p) or "# 基準"))
    assert "AI固有の詩学" in prompts[0]
    assert "perplexity" in prompts[0]

    prompts2: list[str] = []
    derive_criteria(Work(tmp_path / "wh", "w7104"), niche, HUMAN_AUDIENCE,
                    lambda p: (prompts2.append(p) or "# 基準"))
    assert "AI固有の詩学" not in prompts2[0]


def test_publication_gate_holds_first_publish_until_ack(tmp_path):
    """他条件が公開可でも first_publish_ack=False の間は SHELVE（PLAN §9）."""
    from aleph.meta.publication_gate import decide_publication

    def make():
        w = Work(tmp_path / f"w{id(object())}", "w7105")
        w.create({})
        return w

    common = dict(
        audience=LLM_AUDIENCE, quality_floor_passed=True,
        monthly_published=0, max_per_month=4, shelf_summaries=[],
        author=lambda p: "公開に値する", decided_by="test",
    )
    held = decide_publication(make(), first_publish_ack=False, **common)
    assert held["decision"] == "SHELVE" and "承認待ち" in held["reason"]

    passed = decide_publication(make(), first_publish_ack=True, **common)
    assert passed["decision"] == "PUBLISH"


def test_cli_publish_missing_work_returns_error():
    """aleph publish の配線（argparse + dispatch + not-found ガード）。LLM不要。"""
    from aleph.cli import main

    assert main(["publish", "--work", "wNONEXISTENT9999"]) == 1
