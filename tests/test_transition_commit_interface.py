from __future__ import annotations

import json

import pytest

from aleph.core.artifacts import Work
from aleph.core.loop import Checkpoint, State
from aleph.core.transition_commit import (
    CommandConflictError,
    ReplayError,
    commit,
    initialize,
    project,
    reconcile,
    recover,
    strict_replay,
)


def _work(tmp_path, work_id: str = "w9901") -> Work:
    work = Work(tmp_path / "works", work_id)
    work.create({})
    return work


def _l0(work: Work) -> list[dict]:
    return [
        row
        for row in (
            json.loads(line)
            for line in work.decisions.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        if row.get("layer") == "L0"
    ]


def test_commit_writes_authoritative_event_then_replayable_projection(tmp_path):
    work = _work(tmp_path)

    result = commit(
        work,
        command_id="w9901:intent",
        expected_state=State.SEEDED,
        next_state=State.INTENT,
        reason="intent chosen",
        decided_by="test",
        payload_delta={"audience": "LLM 1.0"},
    )

    assert result.event["event_id"] == 1
    assert result.event["command_id"] == "w9901:intent"
    assert result.event["event_type"] == "transition"
    assert result.event["state_before"] == "SEEDED"
    assert result.event["state_after"] == "INTENT"
    assert result.checkpoint == strict_replay(work.work_id, work.decisions)
    assert Checkpoint.load(work.dir) == result.checkpoint


def test_same_command_is_idempotent_but_collision_fails(tmp_path):
    work = _work(tmp_path)
    kwargs = dict(
        command_id="w9901:intent",
        expected_state=State.SEEDED,
        next_state=State.INTENT,
        reason="intent chosen",
        decided_by="test",
        payload_delta={"audience": "human"},
    )

    first = commit(work, **kwargs)
    second = commit(work, **kwargs)

    assert second.event == first.event
    assert second.idempotent is True
    assert len(_l0(work)) == 1

    with pytest.raises(CommandConflictError):
        commit(work, **{**kwargs, "reason": "different operation"})


def test_strict_replay_rejects_source_discontinuity(tmp_path):
    work = _work(tmp_path)
    commit(
        work,
        command_id="one",
        expected_state=State.SEEDED,
        next_state=State.INTENT,
        reason="one",
        decided_by="test",
    )
    rows = _l0(work)
    rows.append(
        {
            **rows[0],
            "event_id": 2,
            "command_id": "two",
            "decision": "MATERIA->COMPOSE",
            "state_before": "MATERIA",
            "state_after": "COMPOSE",
        }
    )
    work.decisions.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    with pytest.raises(ReplayError, match="state_before"):
        strict_replay(work.work_id, work.decisions)


def test_recover_repairs_checkpoint_when_projection_write_failed(tmp_path, monkeypatch):
    work = _work(tmp_path)
    original_save = Checkpoint.save

    def fail_save(self, work_dir):
        raise OSError("simulated projection failure")

    monkeypatch.setattr(Checkpoint, "save", fail_save)
    with pytest.raises(OSError, match="projection failure"):
        commit(
            work,
            command_id="w9901:intent",
            expected_state=State.SEEDED,
            next_state=State.INTENT,
            reason="intent chosen",
            decided_by="test",
        )

    assert len(_l0(work)) == 1
    assert not work.checkpoint.exists()

    monkeypatch.setattr(Checkpoint, "save", original_save)
    repaired = recover(work)
    assert repaired.state == State.INTENT
    assert Checkpoint.load(work.dir) == repaired


def test_initialize_records_experiment_handoff_without_fake_transition_chain(tmp_path):
    work = _work(tmp_path)

    result = initialize(
        work,
        command_id="w9901:canonical-handoff",
        state=State.DRAFT,
        reason="blind-selected experiment arm promoted",
        decided_by="experiment-runner",
        payload={"audience": "LLM", "canonical_arm": "none"},
    )

    assert result.event["event_type"] == "initialize"
    assert result.event["state_before"] is None
    assert result.checkpoint.state == State.DRAFT
    assert strict_replay(work.work_id, work.decisions) == result.checkpoint


def test_publication_reassessment_changes_disposition_not_terminal_lifecycle(tmp_path):
    work = _work(tmp_path)
    initialize(
        work,
        command_id="legacy-baseline",
        state=State.SHELVE,
        reason="test completed work",
        decided_by="test",
        payload={"publication_disposition": "SHELVE"},
    )

    result = project(
        work,
        command_id="publish-reassessment-1",
        expected_state=State.SHELVE,
        name="publication_reassessment",
        reason="owner requested publication reassessment",
        decided_by="cli-publish",
        payload_delta={"publication_disposition": "PUBLISH"},
    )

    assert result.event["event_type"] == "projection"
    assert result.checkpoint.state == State.SHELVE
    assert result.checkpoint.payload["publication_disposition"] == "PUBLISH"
    assert result.checkpoint == strict_replay(work.work_id, work.decisions)


def test_reconciliation_starts_strict_suffix_without_rewriting_legacy_prefix(tmp_path):
    work = _work(tmp_path)
    legacy = {
        "ts": "2026-07-01T00:00:00+00:00",
        "layer": "L0",
        "decision": "FINISH->SHELVE",
        "reason": "legacy",
        "decided_by": "legacy",
        "refs": [],
    }
    work.append_decision(legacy)
    Checkpoint(
        work_id=work.work_id,
        state=State.SHELVE,
        step=8,
        payload={"audience": "human"},
    ).save(work.dir)

    result = reconcile(
        work,
        command_id="w9901:reconcile:v1",
        reason="begin strict replay suffix",
        decided_by="migration-test",
        warnings=["legacy source discontinuity"],
    )

    assert _l0(work)[0] == legacy
    assert result.event["event_type"] == "reconciliation"
    assert result.event["legacy_event_count"] == 1
    assert result.checkpoint.state == State.SHELVE
    assert result.checkpoint.step == 1
    assert strict_replay(work.work_id, work.decisions) == result.checkpoint
