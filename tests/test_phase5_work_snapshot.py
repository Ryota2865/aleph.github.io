from __future__ import annotations

import json
from pathlib import Path

from aleph.core.artifacts import Work
from aleph.core.loop import State
from aleph.core.repository_snapshot import RepositoryReader
from aleph.core.transition_commit import commit, initialize
from aleph.core.work_snapshot import WorkReader


ROOT = Path(__file__).resolve().parents[1]


def test_w0009_reads_resource_stop_without_rewriting_artifacts():
    snapshot = WorkReader(ROOT / "works" / "w0009").snapshot()

    assert snapshot.termination is not None
    assert snapshot.termination.stop_path == "budget"
    assert snapshot.termination.category == "resource_stop"
    assert snapshot.termination.inferred is False
    assert snapshot.author_epoch is None


def test_modern_stop_signal_and_l7_category_are_reconciled(tmp_path):
    work = Work(tmp_path / "works", "w9500")
    work.create({"hint": "fixture"})
    initialize(
        work,
        command_id="init",
        state=State.FINISH,
        reason="予算切れ",
        decided_by="test",
        payload={"stop_path": "budget"},
    )
    work.append_decision(
        {
            "ts": "2026-01-01",
            "layer": "L7",
            "decision": "failure_category:aesthetic_failure",
            "reason": "incorrect fixture",
            "decided_by": "test",
        }
    )
    commit(
        work,
        command_id="shelve",
        expected_state=State.FINISH,
        next_state=State.SHELVE,
        reason="予算切れ",
        decided_by="test",
        payload_delta={"stop_path": "budget"},
    )

    snapshot = WorkReader(work.dir).snapshot()

    assert snapshot.termination is not None
    assert snapshot.termination.category == "aesthetic_failure"
    assert any("termination mismatch" in warning for warning in snapshot.warnings)


def test_author_epoch_is_read_only_from_colophon(tmp_path):
    work = Work(tmp_path / "works", "w9501")
    work.create({"hint": "fixture"})
    (work.dir / "colophon.json").write_text(
        json.dumps({"poetics_version": 1, "author_epoch": "author-fable5-v1"}),
        encoding="utf-8",
    )

    snapshot = WorkReader(work.dir).snapshot()

    assert snapshot.author_epoch == "author-fable5-v1"
    assert snapshot.provenance["author_epoch"] == ("colophon.json#author_epoch",)


def test_legacy_quality_stop_is_display_only_inference(tmp_path):
    work = Work(tmp_path / "works", "w9502")
    work.create({"hint": "fixture"})
    work.append_decision(
        {
            "ts": "2026-01-01",
            "layer": "L0",
            "decision": "FINISH->SHELVE",
            "reason": "品質の床を通過しなかった",
            "decided_by": "test",
            "payload": {"stop_path": "quality_floor"},
        }
    )
    from aleph.core.loop import Checkpoint

    Checkpoint(work.work_id, State.SHELVE, 1, {"stop_path": "quality_floor"}).save(work.dir)

    snapshot = WorkReader(work.dir).snapshot()

    assert snapshot.termination is not None
    assert snapshot.termination.category == "aesthetic_failure"
    assert snapshot.termination.inferred is True


def test_repository_warns_instead_of_aggregating_across_author_epochs(tmp_path):
    for work_id, epoch in (("w9503", "author-a"), ("w9504", "author-b")):
        work = Work(tmp_path / "works", work_id)
        work.create({"hint": "fixture"})
        (work.dir / "colophon.json").write_text(
            json.dumps({"poetics_version": 1, "author_epoch": epoch}), encoding="utf-8"
        )

    snapshot = RepositoryReader(tmp_path).snapshot()

    assert any("cross-author-epoch" in warning for warning in snapshot.warnings)
