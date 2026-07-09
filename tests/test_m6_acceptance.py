"""M6 受入基準（PLAN §10 M6・§3・§8）— 施工対象。施工完了時に全て緑になること.

実行: pytest -m m6
閉ループ配線(SEEDED→…→終端)・志向層・公開層(二層構造/credits/CC0/llms.txt)を
偽依存で固定する。「実LLMでの完全な1周と3作品」はM6実ランで検証（二層方式）。
配線は aleph/pipeline.py に置き、core/loop.py の正典遷移表は変更しない。
テストを弱める変更（assertの削除・skip追加）は監査で不合格となる。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aleph.core.artifacts import Work
from aleph.core.loop import State

pytestmark = pytest.mark.m6


# ---------------------------------------------------------------- 偽依存
class FakeDeps:
    """pipeline.run_work に注入する偽の各層。呼ばれた層を記録する."""

    def __init__(self, audience="人間 0.8 / 自分 0.2", publish_decision="PUBLISH"):
        self.called: list[str] = []
        self.audience = audience
        self.publish_decision = publish_decision

    # L1
    def choose_intent(self, work):
        self.called.append("intent")
        work.intent.write_text(f"# 志向\n{self.audience}\n理由書: テスト", encoding="utf-8")
        return self.audience

    # L2
    def explore(self, work):
        self.called.append("explore")
        work.niche.mkdir(exist_ok=True)
        (work.niche / "report.md").write_text("## n1: テストニッチ", encoding="utf-8")
        return {"id": "n1", "description": "テストニッチ", "vacancy_type": "未着手型"}

    # L3
    def gather_materials(self, work, niche):
        self.called.append("materia")
        (work.materials / "m1.json").write_text(
            json.dumps({"content": "素材", "source": {}, "method": "test", "tags": []},
                       ensure_ascii=False), encoding="utf-8")
        return [{"content": "素材"}]

    # L4+L5
    def compose_and_draft(self, work, niche, audience, materials):
        self.called.append("draft")
        (work.compositions / "criteria.md").write_text("# 基準", encoding="utf-8")
        work.draft_path(1).write_text("本文v1。" * 50, encoding="utf-8")
        return work.draft_path(1)

    # L6+閉ループ
    def critique_and_revise(self, work, audience):
        self.called.append("critique")
        work.review_path(1).write_text("# 査読v1", encoding="utf-8")
        (work.dir / "reviews" / "trajectory.jsonl").write_text(
            json.dumps({"version": 1, "mean_score": 7.0, "disagreement": 1.0}) + "\n",
            encoding="utf-8")
        work.draft_path(2).write_text("本文v2。" * 50, encoding="utf-8")
        return 2

    # L7
    def decide_stop(self, work):
        self.called.append("stop")
        return {"stop": True, "path": "convergence", "reason": "テスト収束"}

    def decide_publication(self, work, audience):
        self.called.append("gate")
        return {"decision": self.publish_decision, "reason": "テスト判定", "comparison": None}


@pytest.fixture
def work(tmp_path):
    w = Work(tmp_path / "works", "w6000")
    w.create({"budget_usd": 1.0})
    return w


# ---------------------------------------------------------------- 志向層
def test_choose_intent_writes_mixture_and_reasons(tmp_path):
    """L1: 宛先は配合比で選ばれ、候補ごとの理由書が intent.md に残る（PLAN §3）.
    「自分」の定義（ALEPHという継続体）がプロンプトに注入される."""
    from aleph.intent.choose import choose_intent

    w = Work(tmp_path, "w6001")
    w.create({})
    prompts: list[str] = []

    def author(p):
        prompts.append(p)
        return json.dumps({"mixture": {"人間": 0.7, "LLM": 0.2, "自分": 0.1},
                           "reasons": {"人間": "理由A", "LLM": "理由B", "自分": "理由C"}},
                          ensure_ascii=False)

    policies = {"intent": {"self_definition": "「自分」とはALEPHという継続体である"}}
    audience = choose_intent(w, author, policies, poetics="簡潔を美とする")
    assert "人間" in audience and "0.7" in audience
    text = w.intent.read_text(encoding="utf-8")
    assert "理由A" in text and "理由C" in text     # 選択理由は監査対象（PLAN §3）
    assert "継続体" in prompts[0]                   # 「自分」の定義注入（§15.6→§3）
    assert "簡潔を美とする" in prompts[0]           # 詩学はL1に常時注入（§7.4）
    decisions = [json.loads(l) for l in w.decisions.read_text(encoding="utf-8").splitlines()]
    assert any(d["layer"] == "L1" for d in decisions)


# ---------------------------------------------------------------- 閉ループ配線
def test_run_work_transits_full_loop_with_checkpoints(work):
    """SEEDED→…→PUBLISH の完全な1周。全遷移がチェックポイントと決定記録を残す（PLAN §2.4）."""
    from aleph.pipeline import run_work
    from aleph.core.loop import Checkpoint

    deps = FakeDeps()
    final = run_work(work, deps, decided_by="pipeline-test")
    assert final == State.PUBLISH
    assert deps.called == ["intent", "explore", "materia", "draft", "critique", "stop", "gate"]

    cp = Checkpoint.load(work.dir)
    assert cp.state == State.PUBLISH
    decisions = [json.loads(l) for l in work.decisions.read_text(encoding="utf-8").splitlines()]
    transitions = [d for d in decisions if "->" in d.get("decision", "")]
    assert len(transitions) >= 8  # SEEDED→INTENT→EXPLORE→MATERIA→COMPOSE→DRAFT→CRITIQUE→FINISH→PUBLISH
    assert (work.final / "text.md").exists()       # 確定稿がfinal/へ（PLAN §2.2）
    meta = json.loads((work.final / "meta.json").read_text(encoding="utf-8"))
    for field in ("credits", "license", "published_at", "intended_reader_models"):
        assert field in meta                        # publish.yaml必須フィールド（PLAN §8）
    assert meta["license"] == "CC0-1.0"


def test_run_work_shelves_when_gate_says_shelve(work):
    """完成≠公開: ゲートがSHELVEなら終端はSHELVE（PLAN §7.3d）."""
    from aleph.pipeline import run_work

    final = run_work(work, FakeDeps(publish_decision="SHELVE"), decided_by="pipeline-test")
    assert final == State.SHELVE


def test_run_work_resumes_from_checkpoint(work):
    """クラッシュ後、チェックポイントの状態から再開し完了できる（PLAN §2.4・§11）."""
    from aleph.pipeline import run_work
    from aleph.core.loop import Checkpoint

    class CrashingDeps(FakeDeps):
        def gather_materials(self, work_, niche):
            raise RuntimeError("simulated crash in L3")

    with pytest.raises(RuntimeError):
        run_work(work, CrashingDeps(), decided_by="pipeline-test")
    cp = Checkpoint.load(work.dir)
    assert cp.state in (State.EXPLORE, State.MATERIA)  # 途中状態が永続化されている

    deps = FakeDeps()
    final = run_work(work, deps, decided_by="pipeline-test")
    assert final == State.PUBLISH
    assert "intent" not in deps.called              # 完了済みの状態はやり直さない


# ---------------------------------------------------------------- 公開層
def make_published_work(tmp_path, work_id="w6100", title="規約"):
    w = Work(tmp_path / "works", work_id)
    w.create({})
    w.final.mkdir(exist_ok=True)
    (w.final / "text.md").write_text(f"# {title}\n本文。", encoding="utf-8")
    (w.final / "meta.json").write_text(json.dumps({
        "title": title, "credits": {"著": "model-a", "査読": ["model-b"]},
        "license": "CC0-1.0", "published_at": "2026-07-10T00:00:00Z",
        "intended_reader_models": ["reader-x/2026"], "provenance": [],
    }, ensure_ascii=False), encoding="utf-8")
    return w


def test_site_build_two_tier_with_credits(tmp_path):
    """静的サイト: 表層=作品ページ(credits/CC0表示)、深層=制作記録へのリンク（PLAN §8・§14.3-9/12）."""
    from aleph.publish.site import build_site

    w = make_published_work(tmp_path)
    out = tmp_path / "docs"
    build_site(works_root=tmp_path / "works", out_dir=out)

    index = (out / "index.html").read_text(encoding="utf-8")
    assert "規約" in index
    page = (out / "works" / "w6100.html").read_text(encoding="utf-8")
    assert "model-a" in page and "CC0" in page      # 名義=関与モデルの列記+ライセンス
    assert "制作記録" in page                        # 深層アーカイブへのリンク（二層構造）


def test_llms_txt_index(tmp_path):
    """LLM宛アーカイブ: llms.txt 形式の索引が生成される（PLAN §8）."""
    from aleph.publish.llm_archive import build_llms_txt

    make_published_work(tmp_path, "w6100", "規約")
    make_published_work(tmp_path, "w6101", "書簡")
    out = tmp_path / "docs"
    out.mkdir(exist_ok=True)
    path = build_llms_txt(works_root=tmp_path / "works", out_dir=out)
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# ")                     # llms.txt 形式（見出し+リスト）
    assert "w6100" in text and "w6101" in text
    assert "reader-x/2026" in text                   # 調律先読者モデル世代の記録（§15.5→§8）
