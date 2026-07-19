from __future__ import annotations

import json

from aleph.core.artifacts import Work
from aleph.core.loop import Checkpoint, State
from aleph.core.transition_commit import initialize
from aleph.core.work_snapshot import Publication, WorkReader


def test_modern_event_replay_wins_over_stale_checkpoint_with_warning(tmp_path):
    work = Work(tmp_path / "works", "w9001")
    work.create({"hint": "fixture"})
    initialize(
        work,
        command_id="fixture",
        state=State.SHELVE,
        reason="fixture",
        decided_by="test",
        payload={"audience": "人間 1.0", "publication_disposition": "SHELVE"},
    )
    Checkpoint(work_id=work.work_id, state=State.FINISH, step=0, payload={}).save(work.dir)

    snapshot = WorkReader(work.dir).snapshot()

    assert snapshot.lifecycle == State.SHELVE
    assert snapshot.publication == Publication.SHELVE
    assert snapshot.audience == "人間 1.0"
    assert any("checkpoint" in warning and "replay" in warning for warning in snapshot.warnings)


def test_selected_published_draft_is_distinct_from_latest_draft(tmp_path):
    work = Work(tmp_path / "works", "w9002")
    work.create({"experiment": {"criteria_constraints": "解除条項"}})
    work.draft_path(1).write_text("採用稿", encoding="utf-8")
    work.draft_path(2).write_text("最新だが退行した稿", encoding="utf-8")
    (work.reviews / "trajectory.jsonl").write_text(
        json.dumps({"version": 1, "mean_score": 8.5}) + "\n"
        + json.dumps({"version": 2, "mean_score": 7.0}) + "\n",
        encoding="utf-8",
    )
    work.append_decision(
        {"ts": "2026-01-01", "layer": "L6", "decision": "採用 v1", "reason": "best", "decided_by": "test", "best_version": 1}
    )
    work.append_decision(
        {"ts": "2026-01-02", "layer": "L0", "decision": "FINISH->PUBLISH", "reason": "publish", "decided_by": "test", "payload": {"audience": "人間 1.0"}}
    )
    Checkpoint("w9002", State.PUBLISH, 1, {"audience": "人間 1.0"}).save(work.dir)
    work.final.mkdir(exist_ok=True)
    (work.final / "text.md").write_text("採用稿", encoding="utf-8")
    (work.final / "meta.json").write_text('{"title":"採用題"}', encoding="utf-8")

    snapshot = WorkReader(work.dir).snapshot()

    assert snapshot.title == "採用題"
    assert snapshot.best_draft is not None and snapshot.best_draft.version == 1
    assert snapshot.best_draft.text == "採用稿"
    assert snapshot.latest_draft is not None and snapshot.latest_draft.version == 2
    assert snapshot.effective_constraints == ("解除条項",)
