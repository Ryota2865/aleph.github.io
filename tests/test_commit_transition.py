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


def test_pipeline_recovers_stale_checkpoint_before_paid_handler(tmp_path):
    """event済み・checkpoint未保存の再開で、完了済みL1を再実行しない."""
    from aleph.pipeline import run_work

    work = Work(tmp_path / "works", "w9206")
    work.create({})

    class StopAfterIntent(_FullLoopDeps):
        def explore(self, work):
            raise RuntimeError("stop after intent")

    with pytest.raises(RuntimeError, match="stop after intent"):
        run_work(work, StopAfterIntent(), decided_by="stale-checkpoint-test")
    assert replay_checkpoint(work.work_id, work.decisions).state == State.EXPLORE

    Checkpoint(work.work_id, State.INTENT, 1, {}).save(work.dir)

    class ResumeDeps(_FullLoopDeps):
        def choose_intent(self, work):
            raise AssertionError("choose_intent must not run again")

        def explore(self, work):
            raise RuntimeError("recovered at explore")

    with pytest.raises(RuntimeError, match="recovered at explore"):
        run_work(work, ResumeDeps(), decided_by="stale-checkpoint-test")


def test_publish_artifact_never_precedes_publish_event(tmp_path, monkeypatch):
    """FINISH->PUBLISH event前に停止しても、finalが公開対象にならない."""
    import aleph.pipeline as pipeline
    from aleph.publish.site import _iter_published

    work = Work(tmp_path / "works", "w9207")
    work.create({})
    original_transition = pipeline._transition

    def stop_before_publish_event(work, current, nxt, *args, **kwargs):
        if current == State.FINISH and nxt == State.PUBLISH:
            raise RuntimeError("stop before publish event")
        return original_transition(work, current, nxt, *args, **kwargs)

    monkeypatch.setattr(pipeline, "_transition", stop_before_publish_event)

    with pytest.raises(RuntimeError, match="stop before publish event"):
        pipeline.run_work(work, _FullLoopDeps(), decided_by="publish-order-test")

    assert replay_checkpoint(work.work_id, work.decisions).state == State.FINISH
    assert list(_iter_published(tmp_path / "works")) == []


def test_pipeline_repairs_final_after_publish_event_crash(tmp_path, monkeypatch):
    """PUBLISH event後のfinal生成失敗は、同じrun commandで補完できる."""
    import aleph.pipeline as pipeline

    work = Work(tmp_path / "works", "w9208")
    work.create({})
    original_finalize = pipeline._finalize_publish

    def fail_finalize(work, deps):
        raise RuntimeError("stop after publish event")

    monkeypatch.setattr(pipeline, "_finalize_publish", fail_finalize)
    with pytest.raises(RuntimeError, match="stop after publish event"):
        pipeline.run_work(work, _FullLoopDeps(), decided_by="publish-repair-test")
    assert replay_checkpoint(work.work_id, work.decisions).state == State.PUBLISH
    assert not (work.final / "meta.json").exists()

    monkeypatch.setattr(pipeline, "_finalize_publish", original_finalize)
    final = pipeline.run_work(work, _FullLoopDeps(), decided_by="publish-repair-test")

    assert final == State.PUBLISH
    assert (work.final / "meta.json").exists()
    assert (work.final / "text.md").exists()


def test_pipeline_repairs_incomplete_final_for_committed_publish(tmp_path):
    """PUBLISH済みの壊れたfinal metadataは、再開時に補完する."""
    from aleph.pipeline import run_work

    work = Work(tmp_path / "works", "w9209")
    work.create({})
    assert run_work(work, _FullLoopDeps(), decided_by="publish-repair-test") == State.PUBLISH
    (work.final / "meta.json").write_text("{", encoding="utf-8")

    assert run_work(work, _FullLoopDeps(), decided_by="publish-repair-test") == State.PUBLISH

    meta = json.loads((work.final / "meta.json").read_text(encoding="utf-8"))
    assert meta["license"] == "CC0-1.0"


def test_pipeline_repairs_final_for_committed_shelve_publication(tmp_path):
    """再監査 finding 5: SHELVE上の正当な公開dispositionもfinalを補完する。"""
    from aleph.core.transition_commit import initialize, project
    from aleph.pipeline import run_work

    work = Work(tmp_path / "works", "w9210")
    work.create({})
    work.draft_path(1).write_text("本文。", encoding="utf-8")
    initialize(
        work,
        command_id="fixture",
        state=State.SHELVE,
        reason="fixture",
        decided_by="test",
    )
    project(
        work,
        command_id="published",
        expected_state=State.SHELVE,
        name="publication_reassessment",
        reason="approved",
        decided_by="test",
        payload_delta={"publication_disposition": "PUBLISH"},
    )

    assert run_work(work, object(), decided_by="publish-repair-test") == State.SHELVE
    assert (work.final / "meta.json").is_file()
    assert (work.final / "text.md").is_file()


def test_publish_event_recovery_runs_poetics_reflection_once(tmp_path, monkeypatch):
    """再監査 finding 5: final故障後の再開でも終端reflectionを一度だけ完了する。"""
    import aleph.pipeline as pipeline

    work = Work(tmp_path / "works", "w9211")
    work.create({})

    class ReflectingDeps(_FullLoopDeps):
        def __init__(self):
            self.reflect_calls = 0

        def reflect_poetics(self, work):
            self.reflect_calls += 1
            return {"applied": False, "diff_reason": "test reflection"}

    deps = ReflectingDeps()
    original_finalize = pipeline._finalize_publish
    monkeypatch.setattr(
        pipeline,
        "_finalize_publish",
        lambda work, deps: (_ for _ in ()).throw(RuntimeError("final failed")),
    )
    with pytest.raises(RuntimeError, match="final failed"):
        pipeline.run_work(work, deps, decided_by="reflection-repair-test")
    assert replay_checkpoint(work.work_id, work.decisions).state == State.PUBLISH
    assert deps.reflect_calls == 0

    monkeypatch.setattr(pipeline, "_finalize_publish", original_finalize)
    assert pipeline.run_work(work, deps, decided_by="reflection-repair-test") == State.PUBLISH
    assert deps.reflect_calls == 1
    assert pipeline.run_work(work, deps, decided_by="reflection-repair-test") == State.PUBLISH
    assert deps.reflect_calls == 1


def test_incomplete_reflection_start_is_not_retried_automatically(tmp_path):
    """開始後の成否不明な課金hookは、owner reconciliationなしに再実行しない。"""
    from aleph.core.transition_commit import initialize
    from aleph.pipeline import run_work

    work = Work(tmp_path / "works", "w9212")
    work.create({})
    work.draft_path(1).write_text("本文。", encoding="utf-8")
    initialize(
        work,
        command_id="fixture",
        state=State.PUBLISH,
        reason="fixture",
        decided_by="test",
    )
    work.append_decision({
        "ts": "2026-07-19T00:00:00+00:00",
        "layer": "L8",
        "decision": "詩学リフレクション開始",
        "reason": "simulated crash after start",
        "decided_by": "test",
    })

    class MustNotReflect:
        def reflect_poetics(self, work):
            raise AssertionError("incomplete reflection must fail closed")

    assert run_work(work, MustNotReflect(), decided_by="reflection-repair-test") == State.PUBLISH
