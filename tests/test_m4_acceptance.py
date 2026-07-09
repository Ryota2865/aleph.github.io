"""M4 受入基準（PLAN §10 M4・§7.1-7.2）— 施工対象。施工完了時に全て緑になること.

実行: pytest -m m4
5審級の査読・REVISEループ・版とスコアの軌跡・敵対的査読の既視性指摘（フィクスチャ）を
偽LLM/偽検索で固定する。最重要契約: **数値スコアは擱筆判断専用であり、authorへの
改稿プロンプトに決して混入しない**（PLAN §7.1 Goodhart回避）。不一致度は必ず記載する。
テストを弱める変更（assertの削除・skip追加）は監査で不合格となる。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from aleph.core.artifacts import Work

pytestmark = pytest.mark.m4

AUDIENCE = "宛先: 人間 0.8 / 自分 0.2"
CRITERIA = "# 基準\n- 反復の音楽性\n- 冷たさと温度差"
DRAFT = "第一条　喪失は、静かに施行される。\n" * 20


def fake_scout(prompt: str) -> str:
    if "技術" in prompt or "破綻" in prompt:
        return json.dumps({"issues": [{"type": "冗長", "where": "第一条", "note": "反復が単調"}]},
                          ensure_ascii=False)
    return json.dumps({"exists": True, "rationale": "類似の規約文学が既にある"}, ensure_ascii=False)


def make_jury(scores):
    jurors = []
    for s in scores:
        def juror(prompt, _s=s):
            return json.dumps({"score": _s, "critique": f"score{_s}の陪審員の批評: 附則が弱い"},
                              ensure_ascii=False)
        jurors.append(juror)
    return jurors


def fake_reader(prompt: str) -> str:
    return json.dumps({"persona": "夜勤明けの読者", "reaction": "第二条で息を呑んだ"}, ensure_ascii=False)


def fake_search(query: str, count: int = 5) -> list[dict]:
    return [{"title": "規約体小説アンソロジー書評", "url": "https://example.com/prior-art",
             "snippet": "条文形式で喪失を描く先行作品群。"}]


@pytest.fixture
def work(tmp_path):
    w = Work(tmp_path, "w2000")
    w.create({"audience": AUDIENCE})
    w.draft_path(1).parent.mkdir(exist_ok=True)
    w.draft_path(1).write_text(DRAFT, encoding="utf-8")
    return w


def tiny_index(tmp_path) -> Path:
    """新奇性査読用の極小プレーン索引（M1形式）."""
    out = tmp_path / "atlas"
    out.mkdir(exist_ok=True)
    vecs = np.eye(4, 8, dtype=np.float32)  # 4チャンク、8次元
    np.save(out / "embeddings.npy", vecs)
    with open(out / "chunks.jsonl", "w", encoding="utf-8") as f:
        for i in range(4):
            f.write(json.dumps({"chunk_id": f"c{i}", "work_id": f"w{i}", "title": f"既存{i}",
                                "author": "a", "seq": 0, "text": "既存テキスト"}, ensure_ascii=False) + "\n")
    (out / "manifest.json").write_text(json.dumps({"n_works": 4, "n_chunks": 4, "dim": 8}))
    return out


class AxisEmbedder:
    """テキスト先頭の数字kで単位ベクトルe_kを返す偽埋め込み（距離を制御可能に）."""
    def __call__(self, texts):
        out = []
        for t in texts:
            v = np.zeros(8, dtype=np.float32)
            v[int(t[0]) if t[:1].isdigit() else 7] = 1.0
            out.append(v)
        return np.asarray(out)


# ---------------------------------------------------------------- 5審級
def test_full_review_has_five_instances(work, tmp_path):
    """5審級（PLAN §7.1: 技術/基準/新奇性/読者/敵対的）が1つの査読報告に揃う."""
    from aleph.critique.review import run_review

    report = run_review(
        work, DRAFT, CRITERIA, AUDIENCE, version=1,
        scout=fake_scout, jury=make_jury([6.0, 9.0, 7.5]), reader=fake_reader,
        embedder=AxisEmbedder(), index_dir=tiny_index(tmp_path),
        search_fn=fake_search,
    )
    for key in ("technical", "criteria_review", "novelty", "reader", "adversary"):
        assert key in report, f"審級 {key} が欠落"
    assert work.review_path(1).exists()  # reviews/v1.md（PLAN §7.1）


def test_jury_disagreement_is_always_reported(work, tmp_path):
    """合意スコアと並んで**不一致度**を必ず記載する（PLAN §7.1・§14.3-8）."""
    from aleph.critique.review import run_review

    report = run_review(work, DRAFT, CRITERIA, AUDIENCE, version=1,
                        scout=fake_scout, jury=make_jury([2.0, 9.0, 5.0]), reader=fake_reader,
                        embedder=AxisEmbedder(), index_dir=tiny_index(tmp_path),
                        search_fn=fake_search)
    cr = report["criteria_review"]
    assert "mean_score" in cr and "disagreement" in cr
    assert cr["disagreement"] > 0
    assert len(cr["critiques"]) == 3  # 各員が独立に採点+論評


def test_novelty_review_measures_atlas_distance(work, tmp_path):
    """新奇性査読は完成稿を埋め込み、アトラス最近傍距離を再測定する（PLAN §7.1-3）."""
    from aleph.critique.review import novelty_review

    index = tiny_index(tmp_path)
    near = novelty_review("0既存クラスタと同方向のテキスト", AxisEmbedder(), index)
    far = novelty_review("7どのクラスタからも遠いテキスト", AxisEmbedder(), index)
    assert far["nearest_dist"] > near["nearest_dist"]


def test_adversary_cites_concrete_prior_art(work):
    """敵対的査読はWeb再検索で既視性を**具体的に**（url+理由つきで）指摘する（PLAN §10 M4受入）."""
    from aleph.critique.adversary import adversary_review

    result = adversary_review(DRAFT, "規約文形式の喪失文学", fake_search, fake_scout)
    assert result["derivative"] is True
    assert len(result["evidence"]) >= 1
    ev = result["evidence"][0]
    assert ev["url"].startswith("http") and ev.get("reason")


# ---------------------------------------------------------------- Goodhart防壁
def test_revise_prompt_carries_critique_but_never_scores(work):
    """改稿指示はauthorへ渡るが、数値スコアと'score'の語は決して渡らない（PLAN §7.1・§16.4）."""
    from aleph.draft.revise import revise

    prompts: list[str] = []
    def author(p: str) -> str:
        prompts.append(p)
        return "改稿された本文。" * 30

    report = {"criteria_review": {"mean_score": 7.5, "disagreement": 3.5,
                                  "critiques": ["附則が弱い", "反復が単調"]},
              "technical": {"issues": [{"note": "冗長"}]},
              "revise_instructions": ["附則を短く", "反復に変奏を"]}
    path = revise(work, report, AUDIENCE, author, version=1)
    assert path == work.draft_path(2) and path.exists()
    assert prompts, "authorが呼ばれていない"
    joined = "\n".join(prompts)
    assert "附則が弱い" in joined and "附則を短く" in joined
    assert "7.5" not in joined and "3.5" not in joined and "score" not in joined.lower()


# ---------------------------------------------------------------- 閉ループ
def test_loop_leaves_version_and_score_trajectory(work, tmp_path):
    """REVISEループが回り、版とスコアの軌跡が残る（PLAN §10 M4・§7.2）."""
    from aleph.critique.review import critique_revise_loop

    def author(p: str) -> str:
        return "改稿本文。" * 40

    final_version = critique_revise_loop(
        work, CRITERIA, AUDIENCE, author,
        scout=fake_scout, jury=make_jury([6.0, 8.0, 7.0]), reader=fake_reader,
        embedder=AxisEmbedder(), index_dir=tiny_index(tmp_path), search_fn=fake_search,
        max_iters=2,
    )
    assert final_version >= 2
    assert work.draft_path(2).exists()          # 改稿版が生成された
    assert work.review_path(1).exists()          # 各版の査読が残る
    traj_path = work.dir / "reviews" / "trajectory.jsonl"
    traj = [json.loads(l) for l in traj_path.read_text(encoding="utf-8").splitlines()]
    assert len(traj) >= 2
    for rec in traj:
        assert "version" in rec and "mean_score" in rec and "disagreement" in rec
    decisions = [json.loads(l) for l in work.decisions.read_text(encoding="utf-8").splitlines()]
    assert any(d["layer"] == "L6" for d in decisions)  # 査読の決定記録（PLAN §2.2）
