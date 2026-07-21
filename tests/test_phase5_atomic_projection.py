from __future__ import annotations

import json

import pytest

from aleph.core.artifacts import Work
from aleph.core.experiment import ExperimentError, ExperimentRun


def _run(tmp_path):
    work = Work(tmp_path / "works", "w9600")
    work.create(
        {
            "experiment": {
                "id": "atomic-jury",
                "hypothesis": "fixture",
                "intervention": "a",
                "control": "b",
                "observations": ["jury"],
                "budget_cap_usd": 1.0,
            }
        }
    )
    return ExperimentRun.open(work.dir)


def _register(run):
    return run.register_jury_batch(
        batch_id="jury-1",
        expected_slots=("j1", "j2", "j3"),
        packet_hash="a" * 64,
        reservation_id="reservation-1",
        semantic_retries=0,
        decided_by="test",
    )


def _slot(run, slot, score=None, *, status="valid"):
    return run.record_jury_slot(
        batch_id="jury-1",
        slot_id=slot,
        attempt=1,
        status=status,
        call_id=f"call-{slot}",
        charge_id=f"charge-{slot}",
        raw_response_hash=(slot * 64)[:64],
        parsed={"score": score, "rationale": "fixture"} if status == "valid" else None,
        decided_by="test",
    )


def test_each_juror_slot_is_durable_before_atomic_projection(tmp_path):
    run = _run(tmp_path)
    _register(run)
    _slot(run, "j1", 7.0)
    _slot(run, "j2", 8.0)
    _slot(run, "j3", status="parse_invalid")

    projection = run.project_jury_batch("jury-1", decided_by="test")

    assert projection["status"] == "INCOMPLETE_PARSE"
    assert projection["valid_slots"] == ["j1", "j2"]
    assert "scores" not in projection
    assert "mean_score" not in projection
    events = run.events()
    assert [event["type"] for event in events].count("jury_slot_recorded") == 3
    persisted = [
        json.loads(line)
        for line in run.events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(row.get("charge_id") == "charge-j2" for row in persisted)


def test_complete_projection_requires_every_slot_and_uses_population_stddev(tmp_path):
    run = _run(tmp_path)
    _register(run)
    _slot(run, "j1", 7.0)
    _slot(run, "j2", 8.0)
    _slot(run, "j3", 9.0)

    projection = run.project_jury_batch("jury-1", decided_by="test")

    assert projection["status"] == "COMPLETE"
    assert projection["mean_score"] == pytest.approx(8.0)
    assert projection["disagreement_stddev"] == pytest.approx((2 / 3) ** 0.5)


def test_unregistered_retry_and_post_projection_mutation_fail_closed(tmp_path):
    run = _run(tmp_path)
    _register(run)
    with pytest.raises(ExperimentError, match="semantic retries"):
        run.record_jury_slot(
            batch_id="jury-1",
            slot_id="j1",
            attempt=2,
            status="valid",
            call_id="call",
            charge_id="charge",
            raw_response_hash="a" * 64,
            parsed={"score": 8.0},
            decided_by="test",
        )
    for slot in ("j1", "j2", "j3"):
        _slot(run, slot, 8.0)
    run.project_jury_batch("jury-1", decided_by="test")
    with pytest.raises(ExperimentError, match="already"):
        run.record_jury_slot(
            batch_id="jury-1",
            slot_id="j1",
            attempt=1,
            status="valid",
            call_id="different",
            charge_id="different",
            raw_response_hash="b" * 64,
            parsed={"score": 9.0},
            decided_by="test",
        )
