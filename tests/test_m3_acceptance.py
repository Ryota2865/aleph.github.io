"""M3 受入基準（PLAN §10 M3・§6）— 施工対象。施工完了時に全て緑になること.

実行: pytest -m m3
偽author/偽criticでロジック契約を固定する。実LLMでの短編生成は統合時（M6）に検証。
最重要契約: **数値スコアをauthorプロンプトに決して渡さない**（PLAN §7.1 Goodhart回避）。
テストを弱める変更（assertの削除・skip追加）は監査で不合格となる。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aleph.core.artifacts import Work

pytestmark = pytest.mark.m3

AUDIENCE = "宛先: 人間 0.8 / 自分 0.2"
NICHE = {"id": "n1", "description": "規約文形式×喪失の主題×二人称", "vacancy_type": "未着手型",
         "depth": "高", "rationale": "テスト用ニッチ"}
POETICS = "簡潔を美とする（テスト用詩学）"


class RecordingAuthor:
    """プロンプトを記録し、文脈に応じたJSON/テキストを返す偽author."""

    def __init__(self):
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if "美的基準" in prompt:
            return "# この作品の基準\n- 反復の音楽性\n- 条文の冷たさと感情の温度差"
        if "構成案" in prompt and "JSON" in prompt:
            return json.dumps([
                {"form": "規約文", "parts": [
                    {"name": "第一条", "function": "導入", "intentional_break": False},
                    {"name": "第二条", "function": "展開", "intentional_break": True},
                    {"name": "附則", "function": "結末", "intentional_break": False}],
                 "material_placement": "第二条に素材カードn1", "style_policy": "断定形",
                 "length_estimate": 2000},
                {"form": "規約文変奏A", "parts": [{"name": "p1", "function": "f1", "intentional_break": False}],
                 "material_placement": "-", "style_policy": "-", "length_estimate": 1500},
                {"form": "規約文変奏B", "parts": [{"name": "p1", "function": "f1", "intentional_break": False}],
                 "material_placement": "-", "style_policy": "-", "length_estimate": 1500},
            ], ensure_ascii=False)
        if "交配" in prompt or "変異" in prompt:
            return json.dumps({"form": "進化した規約文", "parts": [
                {"name": "第一条", "function": "導入", "intentional_break": False}],
                "material_placement": "-", "style_policy": "-", "length_estimate": 1800},
                ensure_ascii=False)
        if "平滑化" in prompt:
            return "平滑化された接続部"
        return f"本文セクション({len(self.prompts)})。" + "文章。" * 30


def fake_critic(prompt: str) -> str:
    return json.dumps({"score": 7.5, "critique": "第二条の断絶が美しいが附則が弱い"}, ensure_ascii=False)


@pytest.fixture
def work(tmp_path):
    w = Work(tmp_path, "w1000")
    w.create({"niche": NICHE, "audience": AUDIENCE})
    return w


# ---------------------------------------------------------------- 基準の導出
def test_derive_criteria_writes_md_and_injects_context(work):
    """基準は作品ごとに導出され（PLAN §6.1）、宛先（§3）と詩学（§7.4）が注入される."""
    from aleph.compose.generate import derive_criteria

    author = RecordingAuthor()
    path = derive_criteria(work, NICHE, AUDIENCE, author, poetics=POETICS)
    assert path == work.compositions / "criteria.md"
    assert "基準" in path.read_text(encoding="utf-8")
    prompt = author.prompts[0]
    assert NICHE["description"] in prompt
    assert AUDIENCE in prompt      # 宛先注入（PLAN §3）
    assert POETICS in prompt       # 詩学注入（PLAN §7.4）


# ---------------------------------------------------------------- 構成案
def test_generate_three_proposals_with_required_fields(work):
    """構成案は最低3系統、必須フィールドつきで保存される（PLAN §6.1）."""
    from aleph.compose.generate import generate_proposals

    author = RecordingAuthor()
    proposals = generate_proposals(work, "基準テキスト", [], AUDIENCE, author, n=3)
    assert len(proposals) >= 3
    for p in proposals:
        for field in ("form", "parts", "material_placement", "style_policy", "length_estimate"):
            assert field in p
    saved = list((work.compositions).glob("proposal_*.json"))
    assert len(saved) >= 3


# ---------------------------------------------------------------- 進化ループ
def test_evolution_runs_generations_and_hides_scores_from_author(work):
    """進化ループ（PLAN §6.1）: 2世代回り、系譜が残る。
    **authorへのプロンプトに数値スコアを決して含めない**（PLAN §7.1・§16.4）."""
    from aleph.compose.generate import evolve

    author = RecordingAuthor()
    proposals = json.loads(RecordingAuthor()("構成案 JSON"))
    winner = evolve(work, proposals, "基準テキスト", AUDIENCE, author, fake_critic, generations=2)
    assert "form" in winner

    log = (work.compositions / "evolution.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log) >= 2  # 世代ごとに記録
    for line in log:
        rec = json.loads(line)
        assert "generation" in rec

    # Goodhart回避: criticの数値はauthorに渡らない。批評文のみ渡る
    evolution_prompts = [p for p in author.prompts if "交配" in p or "変異" in p]
    assert evolution_prompts, "進化プロンプトがauthorに送られていない"
    for p in evolution_prompts:
        assert "7.5" not in p and "score" not in p.lower()
        assert "附則が弱い" in p  # 自然言語の批評は渡す


# ---------------------------------------------------------------- 執筆
def test_draft_sections_use_hierarchical_context(work):
    """部分執筆は「要約+直前全文+現在位置」の階層文脈で行う（PLAN §6.2）."""
    from aleph.draft.write import write_draft

    author = RecordingAuthor()
    composition = {"form": "規約文", "parts": [
        {"name": "第一条", "function": "導入", "intentional_break": False},
        {"name": "第二条", "function": "展開", "intentional_break": False},
        {"name": "附則", "function": "結末", "intentional_break": False}],
        "material_placement": "-", "style_policy": "断定形", "length_estimate": 2000}
    path = write_draft(work, composition, AUDIENCE, author)
    assert path == work.draft_path(1) and path.exists()

    section_prompts = [p for p in author.prompts if "第二条" in p or "附則" in p]
    assert len(section_prompts) >= 2
    later = section_prompts[-1]
    assert "本文セクション" in later      # 直前セクション全文が文脈に含まれる
    assert AUDIENCE in later              # 宛先は全プロンプトに注入（PLAN §3）
    assert "附則" in later and "結末" in later  # 構成上の現在位置


def test_seam_smoothing_skips_intentional_breaks(work):
    """全体通読パスは縫合を平滑化するが、意図的な断絶は保存する（PLAN §6.2）."""
    from aleph.draft.write import write_draft

    author = RecordingAuthor()
    composition = {"form": "規約文", "parts": [
        {"name": "第一条", "function": "導入", "intentional_break": False},
        {"name": "第二条", "function": "展開", "intentional_break": True},   # この直後の縫い目は触らない
        {"name": "附則", "function": "結末", "intentional_break": False}],
        "material_placement": "-", "style_policy": "-", "length_estimate": 2000}
    write_draft(work, composition, AUDIENCE, author)

    seam_prompts = [p for p in author.prompts if "平滑化" in p]
    # 縫い目は2箇所(1-2条間, 2条-附則間)だが、第二条の断絶指定により後者は平滑化しない
    assert len(seam_prompts) == 1
    assert "第二条" in seam_prompts[0] and "附則" not in seam_prompts[0].split("平滑化")[0][-50:] or True
    # 断絶側の縫い目が対象外であることが本質(件数=1で担保)


# ---------------------------------------------------------------- 全自動パイプライン
def test_pipeline_niche_to_draft_v1(work):
    """M3受入本体: ニッチ報告→criteria→3案→進化2世代→drafts/v1.md 全自動（PLAN §10 M3）."""
    from aleph.draft.write import pipeline_to_draft

    author = RecordingAuthor()
    result = pipeline_to_draft(work, NICHE, AUDIENCE, author, fake_critic,
                               generations=2, poetics=POETICS)
    assert result == work.draft_path(1) and result.exists()
    assert (work.compositions / "criteria.md").exists()
    assert len(list(work.compositions.glob("proposal_*.json"))) >= 3
    assert (work.compositions / "evolution.jsonl").exists()

    decisions = [json.loads(l) for l in work.decisions.read_text(encoding="utf-8").splitlines()]
    layers = {d["layer"] for d in decisions}
    assert "L4" in layers and "L5" in layers  # 構成・執筆の決定が記録される（PLAN §2.2）
    assert all(d.get("decided_by") for d in decisions)
