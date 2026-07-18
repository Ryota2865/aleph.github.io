"""commit_transitionの第一歩（PLAN_CHANGELOG 0.7.18-1、Fable5設計者審査 問1）.

「decisions.jsonlが正、checkpoint.jsonはそこから再構築可能な投影である」という
決定を、実際に検証可能な契約として固定する: 完全な1周を実行した後、
`Checkpoint.load(work.dir)` と `replay_checkpoint(work.work_id, work.decisions)` が
一致することを確認する。「再構築可能」と「再構築を検証している」は別物、という
Fable5の指摘への対応。

実行: pytest -m m6
"""
from __future__ import annotations

import json

import pytest

from aleph.core.artifacts import Work
from aleph.core.loop import Checkpoint, State, replay_checkpoint

pytestmark = pytest.mark.m6


class _FullLoopDeps:
    """SEEDED→PUBLISHまでの全遷移を一通り踏むための最小deps."""

    def choose_intent(self, work):
        return "人間 0.8 / 自分 0.2"

    def explore(self, work):
        return {"id": "n1", "description": "テストニッチ", "vacancy_type": "未着手型"}

    def gather_materials(self, work, niche):
        return [{"content": "素材1"}, {"content": "素材2"}]

    def compose_and_draft(self, work, niche, audience, materials):
        work.draft_path(1).write_text("本文v1。" * 50, encoding="utf-8")

    def critique_and_revise(self, work, audience):
        work.draft_path(2).write_text("本文v2。" * 50, encoding="utf-8")
        return 2

    def decide_stop(self, work):
        return {"stop": True, "path": "convergence", "reason": "テスト収束"}

    def decide_publication(self, work, audience):
        return {"decision": "PUBLISH", "reason": "テスト公開"}


def test_checkpoint_equals_replay_after_full_run(tmp_path):
    """完全な1周後、checkpoint.jsonとreplay_checkpoint(decisions.jsonl)が一致する."""
    from aleph.pipeline import run_work

    work = Work(tmp_path / "works", "w9201")
    work.create({})

    final = run_work(work, _FullLoopDeps(), decided_by="commit-transition-test")
    assert final == State.PUBLISH

    checkpoint = Checkpoint.load(work.dir)
    replayed = replay_checkpoint(work.work_id, work.decisions)

    assert replayed.work_id == checkpoint.work_id
    assert replayed.state == checkpoint.state
    assert replayed.step == checkpoint.step
    assert replayed.payload == checkpoint.payload


def test_checkpoint_equals_replay_after_partial_run_and_resume(tmp_path):
    """途中(CRITIQUE)で終わった作品を再開しても、再開後のcheckpointとreplayが一致する."""
    from aleph.pipeline import run_work

    work = Work(tmp_path / "works", "w9202")
    work.create({})

    class StallingDeps(_FullLoopDeps):
        def decide_stop(self, work):
            raise RuntimeError("simulated crash before FINISH")

    with pytest.raises(RuntimeError):
        run_work(work, StallingDeps(), decided_by="commit-transition-test")

    # クラッシュ後のcheckpointはCRITIQUE到達直前まで進んでいるはず
    mid_checkpoint = Checkpoint.load(work.dir)
    mid_replayed = replay_checkpoint(work.work_id, work.decisions)
    assert mid_replayed.state == mid_checkpoint.state
    assert mid_replayed.step == mid_checkpoint.step
    assert mid_replayed.payload == mid_checkpoint.payload

    final = run_work(work, _FullLoopDeps(), decided_by="commit-transition-test")
    assert final == State.PUBLISH
    checkpoint = Checkpoint.load(work.dir)
    replayed = replay_checkpoint(work.work_id, work.decisions)
    assert replayed.state == checkpoint.state
    assert replayed.step == checkpoint.step
    assert replayed.payload == checkpoint.payload


def test_replay_accumulates_incremental_payload_across_transitions(tmp_path):
    """L0記録は差分payloadのみを持つが、replayは累積して全ctxを復元する."""
    from aleph.pipeline import run_work

    work = Work(tmp_path / "works", "w9203")
    work.create({})
    run_work(work, _FullLoopDeps(), decided_by="commit-transition-test")

    decisions = [json.loads(l) for l in work.decisions.read_text(encoding="utf-8").splitlines()]
    l0 = [d for d in decisions if d["layer"] == "L0"]
    assert any(d.get("payload") for d in l0), "差分payloadが一つも記録されていない"
    # 個々のL0記録は全ctxではなく差分のみ（materialsを含むのは1件だけのはず）
    with_materials = [d for d in l0 if "materials" in (d.get("payload") or {})]
    assert len(with_materials) == 1

    replayed = replay_checkpoint(work.work_id, work.decisions)
    assert "materials" in replayed.payload
    assert "niche" in replayed.payload
    assert "audience" in replayed.payload


def test_checkpoint_save_is_atomic_no_partial_file_left_behind(tmp_path):
    """Checkpoint.saveは一時ファイル経由で書き、正常終了後にtmpファイルが残らない."""
    work_dir = tmp_path / "w9204"
    work_dir.mkdir()
    Checkpoint(work_id="w9204", state=State.INTENT, step=1, payload={"a": 1}).save(work_dir)

    files = list(work_dir.glob("*.tmp"))
    assert files == []
    assert (work_dir / "checkpoint.json").exists()


def test_pipeline_recovers_from_event_stream_when_checkpoint_is_missing(tmp_path):
    """複数event後にprojectionだけ消えても、完了済みlayerを再実行しない."""
    from aleph.pipeline import run_work

    work = Work(tmp_path / "works", "w9205")
    work.create({})

    class CrashAtCritique(_FullLoopDeps):
        def decide_stop(self, work):
            raise RuntimeError("stop before FINISH")

    with pytest.raises(RuntimeError):
        run_work(work, CrashAtCritique(), decided_by="checkpoint-loss-test")
    assert Checkpoint.load(work.dir).state == State.CRITIQUE
    work.checkpoint.unlink()

    called: list[str] = []

    class ResumeDeps(_FullLoopDeps):
        def choose_intent(self, work):
            called.append("intent")
            return super().choose_intent(work)

        def explore(self, work):
            called.append("explore")
            return super().explore(work)

        def gather_materials(self, work, niche):
            called.append("materia")
            return super().gather_materials(work, niche)

        def compose_and_draft(self, work, niche, audience, materials):
            called.append("draft")
            return super().compose_and_draft(work, niche, audience, materials)

    final = run_work(work, ResumeDeps(), decided_by="checkpoint-loss-test")

    assert final == State.PUBLISH
    assert called == []
    assert Checkpoint.load(work.dir) == replay_checkpoint(work.work_id, work.decisions)
