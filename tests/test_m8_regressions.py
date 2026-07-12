from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from aleph.core.artifacts import Work
from aleph.core.llm import LLMResponse, TokenLogprob, Usage

pytestmark = pytest.mark.m6

HUMAN_AUDIENCE = "人間 0.8 / LLM 0.1 / 自分 0.1"
LLM_AUDIENCE = "LLM 0.7 / 人間 0.2 / 自分 0.1"


def _work(tmp_path: Path, work_id: str = "w8000") -> Work:
    work = Work(tmp_path, work_id)
    work.create({})
    return work


def _tiny_index(tmp_path: Path) -> Path:
    out = tmp_path / "atlas"
    out.mkdir(exist_ok=True)
    np.save(out / "embeddings.npy", np.ones((1, 8), dtype=np.float32))
    (out / "chunks.jsonl").write_text(
        json.dumps({"chunk_id": "c1", "work_id": "w1", "title": "既存", "author": "a"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    (out / "manifest.json").write_text(json.dumps({"n_works": 1, "n_chunks": 1, "dim": 8}), encoding="utf-8")
    return out


class ConstantEmbedder:
    def __call__(self, texts):
        return np.ones((len(texts), 8), dtype=np.float32)


def _scout(prompt: str) -> str:
    if "直すべき点" in prompt:
        return ""
    if '"issues"' in prompt:
        return json.dumps({"issues": []}, ensure_ascii=False)
    return json.dumps({"exists": False, "rationale": "既視性なし"}, ensure_ascii=False)


def _reader(prompt: str) -> str:
    return json.dumps({"reaction": "ok"}, ensure_ascii=False)


def _search(*args, **kwargs) -> list[dict]:
    return []


def _juror(critique: str = "よい", prompts: list[str] | None = None):
    def juror(prompt: str) -> str:
        if prompts is not None:
            prompts.append(prompt)
        return json.dumps({"score": 8.0, "critique": critique}, ensure_ascii=False)

    return juror


def test_long_review_input_includes_tail_climax_marker(tmp_path):
    from aleph.critique.review import run_review

    work = _work(tmp_path)
    marker = "__CLIMAX_MARKER__"
    draft = "冒頭" + ("A" * 9000) + "中間" + ("B" * 9000) + marker
    juror_prompts: list[str] = []

    run_review(
        work,
        draft,
        "基準",
        HUMAN_AUDIENCE,
        version=1,
        scout=_scout,
        jury=[_juror(prompts=juror_prompts)],
        reader=_reader,
        embedder=ConstantEmbedder(),
        index_dir=_tiny_index(tmp_path),
        search_fn=_search,
    )

    assert juror_prompts
    assert marker in juror_prompts[0]
    assert "末尾（クライマックス）" in juror_prompts[0]
    assert f"全文{len(draft)}字" in juror_prompts[0]


def test_revise_instruction_distillation_keeps_only_issues():
    from aleph.critique.review import _synthesize_revise_instructions

    praise_only = _synthesize_revise_instructions(
        {"critiques": ["余白が美しく、結末も鮮やか。"]},
        {"issues": []},
        lambda prompt: "",
    )
    assert praise_only == []

    def issue_scout(prompt: str) -> str:
        assert "褒め言葉は除いてください" in prompt
        return "- 附則が弱い\n- 反復が冗長"

    instructions = _synthesize_revise_instructions(
        {"critiques": ["美しいが、附則が弱い。score 9.0"]},
        {"issues": []},
        issue_scout,
    )
    joined = "\n".join(instructions)
    assert "附則が弱い" in joined
    assert "反復が冗長" in joined
    assert "美しい" not in joined
    assert "9.0" not in joined
    assert "score" not in joined.lower()
    assert "スコア" not in joined


def test_llm_primary_audience_records_perplexity_curve(tmp_path):
    from aleph.critique.review import run_review

    work = _work(tmp_path)

    def reader_llm(messages, **kwargs):
        assert kwargs.get("logprobs") is True
        return LLMResponse(
            text="ok",
            model="fake",
            provider="fake",
            usage=Usage(prompt_tokens=1, completion_tokens=2),
            cost_usd=0.0,
            logprobs=(
                TokenLogprob(token="a", logprob=-3.0),
                TokenLogprob(token="b", logprob=-1.0),
            ),
        )

    report = run_review(
        work,
        "第一節\n本文",
        "基準",
        LLM_AUDIENCE,
        version=1,
        scout=_scout,
        jury=[_juror()],
        reader=_reader,
        embedder=ConstantEmbedder(),
        index_dir=_tiny_index(tmp_path),
        search_fn=_search,
        reader_llm=reader_llm,
    )

    assert report["perplexity"]["curve"] == pytest.approx([-2.0])
    assert "perplexity" in work.review_path(1).read_text(encoding="utf-8")


def test_non_llm_audience_skips_perplexity_curve(tmp_path):
    from aleph.critique.review import run_review

    work = _work(tmp_path)

    def reader_llm(messages, **kwargs):
        raise AssertionError("非LLM宛ではreader_llmを呼ばない")

    report = run_review(
        work,
        "第一節\n本文",
        "基準",
        HUMAN_AUDIENCE,
        version=1,
        scout=_scout,
        jury=[_juror()],
        reader=_reader,
        embedder=ConstantEmbedder(),
        index_dir=_tiny_index(tmp_path),
        search_fn=_search,
        reader_llm=reader_llm,
    )

    assert "perplexity" not in report
    assert "perplexity" not in work.review_path(1).read_text(encoding="utf-8")


def test_write_draft_records_perspective_deviation_without_rewriting(tmp_path):
    from aleph.draft.write import write_draft

    work = _work(tmp_path)
    composition = {
        "parts": [{"name": "一", "function": "導入", "intentional_break": False}],
        "style_policy": "三人称で統一",
    }

    path = write_draft(work, composition, HUMAN_AUDIENCE, lambda prompt: "私は戸口に立った。")

    assert path.read_text(encoding="utf-8") == "私は戸口に立った。"
    decisions = [json.loads(line) for line in work.decisions.read_text(encoding="utf-8").splitlines()]
    assert any(
        decision.get("layer") == "L5" and decision.get("decision", "").startswith("構成逸脱:")
        for decision in decisions
    )


def test_overused_ai_syntax_adds_rationing_instruction():
    from aleph.critique.review import _synthesize_revise_instructions

    draft = "近いほど、遠い。深いほど、軽い。読むほど、遅い。進むほど、戻る。"
    instructions = _synthesize_revise_instructions(
        {"critiques": []},
        {"issues": []},
        lambda prompt: "",
        draft_text=draft,
    )

    joined = "\n".join(instructions)
    assert "AI紋の配給" in joined
    assert "特定の人物/箇所に限定" in joined


def test_publish_intent_string_false_is_shelve(tmp_path):
    """監査 finding 2: JSON の "publish": "false"（文字列）を PUBLISH と誤判定しない."""
    from aleph.meta.publication_gate import decide_publication

    work = _work(tmp_path, "w8100")

    def author(p):
        if "公開するか判断" in p:
            return json.dumps({"publish": "false", "reason": "まだ棚に"}, ensure_ascii=False)
        return "比較論述"

    result = decide_publication(
        work, audience="人間 0.9 / 自分 0.1", quality_floor_passed=True,
        monthly_published=0, max_per_month=4, shelf_summaries=[], author=author, decided_by="t",
    )
    assert result["decision"] == "SHELVE"


def test_distillation_keeps_missing_element_issues():
    """監査 finding 4: 『伏線がありません』等の欠落指摘は捨てない（『問題ありません』は捨てる）."""
    from aleph.critique.review import _synthesize_revise_instructions

    def scout(prompt):
        return "- 結末への伏線がありません\n- 問題ありません"

    instructions = _synthesize_revise_instructions(
        {"critiques": ["伏線が不足している"]}, {"issues": []}, scout,
    )
    joined = "\n".join(instructions)
    assert "伏線がありません" in joined
    assert "問題ありません" not in joined


def test_high_disagreement_versions_reserved_as_border_stimuli(tmp_path):
    """陪審不一致が閾超の版を E-border 刺激として予約する（Fable5提案 2026-07-13）。冪等."""
    from aleph.pipeline import reserve_border_candidates

    work = _work(tmp_path / "works", "w8200")
    rows = [
        {"version": 1, "mean_score": 7.0, "disagreement": 0.4, "instructions": []},
        {"version": 2, "mean_score": 6.8, "disagreement": 1.3, "instructions": []},
    ]
    reviews = work.dir / "reviews"
    reviews.mkdir(exist_ok=True)
    (reviews / "trajectory.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8",
    )
    queue = tmp_path / "queue.jsonl"
    first = reserve_border_candidates(work, queue_path=queue)
    assert [r["version"] for r in first] == [2]
    again = reserve_border_candidates(work, queue_path=queue)
    assert again == []  # 冪等
    recs = [json.loads(l) for l in queue.read_text(encoding="utf-8").splitlines()]
    assert len(recs) == 1 and recs[0]["disagreement"] == 1.3
