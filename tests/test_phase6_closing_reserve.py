"""Phase 6 closing reserve is derived from versioned slot ceilings."""
from __future__ import annotations

from copy import deepcopy

import pytest

from aleph.core.budget import RunBudgetPlan

_HASH = "b" * 64


def _manifest() -> dict:
    return {
        "version": 2,
        "cap_amount": 1.15,
        "pools": {"player": 0.5, "held_out": 0.25, "closing": 0.4},
        "batches": [
            {
                "batch_id": "player",
                "pool": "player",
                "role": "author_primary",
                "max_amount": 0.5,
                "phases": ["L1"],
                "expected_slots": ["intent"],
                "input_manifest_hash": _HASH,
            },
            {
                "batch_id": "held-out",
                "pool": "held_out",
                "role": "critic_jury",
                "max_amount": 0.25,
                "phases": ["L6"],
                "expected_slots": ["jury"],
                "input_manifest_hash": _HASH,
            },
            {
                "batch_id": "close",
                "pool": "closing",
                "role": "author_primary",
                "max_amount": 0.4,
                "phases": ["L7"],
                "expected_slots": ["publication", "title", "final-projection"],
                "input_manifest_hash": _HASH,
            },
        ],
        "closing_slots": [
            {
                "slot_id": "publication",
                "batch_id": "close",
                "kind": "external",
                "provider": "anthropic",
                "model": "claude-fable-5",
                "pricing_version": "anthropic-2026-07-01",
                "axes": [
                    {
                        "name": "input_tokens",
                        "unit_ceiling": 10_000,
                        "usd_per_unit": 10.0 / 1_000_000,
                    },
                    {
                        "name": "output_tokens",
                        "unit_ceiling": 6_000,
                        "usd_per_unit": 50.0 / 1_000_000,
                    },
                ],
            },
            {
                "slot_id": "title",
                "batch_id": "close",
                "kind": "deterministic",
            },
            {
                "slot_id": "final-projection",
                "batch_id": "close",
                "kind": "deterministic",
            },
        ],
    }


def test_derives_closing_reserve_and_preserves_pricing_identity() -> None:
    plan = RunBudgetPlan.from_manifest(_manifest(), work_id="w0010")

    assert plan.version == 2
    assert plan.closing_reserve == pytest.approx(0.4)
    assert [slot.max_amount for slot in plan.closing_slots] == [pytest.approx(0.4), 0, 0]
    assert plan.closing_slots[0].canonical()["pricing_version"] == "anthropic-2026-07-01"
    assert len(plan.manifest_hash) == 64
    assert all(
        batch.run_manifest_hash == plan.manifest_hash
        and batch.protected_definition_version == "phase6-run-budget-v2"
        for batch in plan.batches
    )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda m: m["closing_slots"][0].pop("pricing_version"),
            "fields must be exactly",
        ),
        (
            lambda m: m["closing_slots"][0]["axes"].pop(),
            "missing required axes",
        ),
        (
            lambda m: m["closing_slots"][0]["axes"][0].update(unit_ceiling=True),
            "unit_ceiling",
        ),
        (
            lambda m: m["closing_slots"][0]["axes"][0].update(usd_per_unit=float("nan")),
            "finite",
        ),
        (
            lambda m: m["closing_slots"].pop(),
            "cover closing expected_slots exactly",
        ),
        (
            lambda m: m["batches"][-1].update(max_amount=0.39),
            "does not match derived slot maximum",
        ),
        (
            lambda m: (m.update(cap_amount=1.16), m["pools"].update(closing=0.41)),
            "does not match derived closing reserve",
        ),
    ],
)
def test_unknown_or_inconsistent_closing_cost_fails_closed(mutate, message: str) -> None:
    manifest = deepcopy(_manifest())
    mutate(manifest)
    with pytest.raises(ValueError, match=message):
        RunBudgetPlan.from_manifest(manifest, work_id="w0010")


def test_v1_remains_readable_as_unverified_legacy_manifest() -> None:
    legacy = deepcopy(_manifest())
    legacy["version"] = 1
    del legacy["closing_slots"]

    plan = RunBudgetPlan.from_manifest(legacy, work_id="w0010")

    assert plan.version == 1
    assert plan.closing_reserve is None
    assert plan.closing_slots == ()
    assert all(
        batch.run_manifest_hash == plan.manifest_hash
        and batch.protected_definition_version == "phase5-run-budget-v1"
        for batch in plan.batches
    )
