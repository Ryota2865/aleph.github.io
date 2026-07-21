"""Strict normal-run protected-budget manifest validation."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from aleph.core.budget import BatchLookupError, RunBudgetPlan

_HASH = "a" * 64


def _batch(
    batch_id: str,
    pool: str,
    role: str,
    amount: float,
    phases: list[str],
) -> dict[str, Any]:
    return {
        "batch_id": batch_id,
        "pool": pool,
        "role": role,
        "max_amount": amount,
        "phases": phases,
        "expected_slots": [f"{batch_id}-slot"],
        "input_manifest_hash": _HASH,
        "semantic_retries": 0,
    }


def _manifest() -> dict[str, Any]:
    return {
        "version": 1,
        "cap_amount": 4.0,
        "pools": {"player": 2.5, "held_out": 1.0, "closing": 0.5},
        "batches": [
            _batch("player-author", "player", "author_primary", 2.5, ["L1", "L2", "L3"]),
            _batch("heldout-juror", "held_out", "critic_jury", 1.0, ["L4-L5"]),
            _batch("closing-author", "closing", "author_primary", 0.5, ["L7"]),
        ],
    }


def test_valid_manifest_derives_scope_and_immutable_routing() -> None:
    plan = RunBudgetPlan.from_manifest(_manifest(), work_id="w0010")

    assert plan.charged_to == "run:w0010"
    assert plan.cap_amount == 4.0
    assert plan.pool_limits == (("player", 2.5), ("held_out", 1.0), ("closing", 0.5))
    assert plan.batch_for("L7", "author_primary").batch_id == "closing-author"
    assert plan.batch_for("L7", "author_primary").phases == ("L7",)
    assert all(batch.ledger == "api" for batch in plan.batches)
    assert all(batch.atomic_projection for batch in plan.batches)
    with pytest.raises(FrozenInstanceError):
        plan.batches = ()  # type: ignore[misc]


def test_routing_is_bound_into_reservation_identity() -> None:
    first = RunBudgetPlan.from_manifest(_manifest(), work_id="w0010").batches[0]
    changed = _manifest()
    changed["batches"][0]["phases"] = ["L2", "L3"]
    second = RunBudgetPlan.from_manifest(changed, work_id="w0010").batches[0]

    assert first.canonical()["phases"] == ["L1", "L2", "L3"]
    assert first.canonical() != second.canonical()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda m: m.update(charged_to="run:evil"), "unknown manifest keys"),
        (lambda m: m.update(scope="experiment:evil"), "unknown manifest keys"),
        (lambda m: m["batches"][0].update(allow_borrow=True), "unknown keys"),
        (lambda m: m.update(version=True), "version"),
        (lambda m: m.update(cap_amount=True), "cap_amount"),
        (lambda m: m["pools"].update(player=True), "pool player"),
        (lambda m: m["batches"][0].update(max_amount=True), "max_amount"),
        (lambda m: m["batches"][0].update(semantic_retries=True), "semantic_retries"),
        (lambda m: m["batches"][0].update(input_manifest_hash="A" * 64), "input_manifest_hash"),
        (lambda m: m["batches"][0].update(input_manifest_hash="g" * 64), "input_manifest_hash"),
        (lambda m: m["batches"][0].update(phases=["L0"]), "not in allowed"),
        (lambda m: m["batches"][0].update(expected_slots=["s", "s"]), "must be unique"),
    ],
)
def test_unsafe_or_malformed_fields_are_rejected(mutate, message: str) -> None:
    manifest = _manifest()
    mutate(manifest)
    with pytest.raises(ValueError, match=message):
        RunBudgetPlan.from_manifest(manifest, work_id="w0010")


@pytest.mark.parametrize("work_id", ["", "   ", None])
def test_work_id_must_be_explicit(work_id) -> None:
    with pytest.raises(ValueError, match="work_id"):
        RunBudgetPlan.from_manifest(_manifest(), work_id=work_id)


def test_pool_totals_must_equal_cap() -> None:
    manifest = _manifest()
    manifest["pools"]["player"] = 2.0
    with pytest.raises(ValueError, match="pool values sum"):
        RunBudgetPlan.from_manifest(manifest, work_id="w0010")


def test_batch_commitments_cannot_exceed_pool() -> None:
    manifest = _manifest()
    manifest["batches"].append(_batch("extra", "player", "scout", 0.1, ["L6"]))
    with pytest.raises(ValueError, match="exceeding pool limit"):
        RunBudgetPlan.from_manifest(manifest, work_id="w0010")


def test_phase_role_route_must_be_unique() -> None:
    manifest = _manifest()
    manifest["batches"].append(_batch("duplicate", "player", "author_primary", 0.1, ["L1"]))
    manifest["batches"][0]["max_amount"] = 2.4
    with pytest.raises(ValueError, match="already covered"):
        RunBudgetPlan.from_manifest(manifest, work_id="w0010")


def test_closing_pool_must_cover_l7() -> None:
    manifest = _manifest()
    manifest["batches"][-1]["phases"] = ["L6"]
    with pytest.raises(ValueError, match="closing-pool batch covering phase L7"):
        RunBudgetPlan.from_manifest(manifest, work_id="w0010")


def test_missing_route_fails_closed() -> None:
    plan = RunBudgetPlan.from_manifest(_manifest(), work_id="w0010")
    with pytest.raises(BatchLookupError, match="no batch covers"):
        plan.batch_for("L6", "author_primary")
