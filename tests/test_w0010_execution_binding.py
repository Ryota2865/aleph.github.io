"""w0010 execution binding remains tied to the result-blind preregistration."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from aleph.core.budget import RunBudgetPlan


ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "designs" / "w0010-archive-epistemology-exit-closure-preregistration.json"
RUN_BUDGET = ROOT / "designs" / "w0010-run-budget-v2.json"
PREREG_SHA256 = "340c5756715f076cf24a5031715617d50344429a6db72952435c92017364b070"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_run_budget_is_bound_to_frozen_result_blind_preregistration() -> None:
    assert hashlib.sha256(PREREG.read_bytes()).hexdigest() == PREREG_SHA256
    prereg = _load(PREREG)
    budget = _load(RUN_BUDGET)

    assert prereg["status"] == "preregistered_not_run"
    assert prereg["baseline"]["w0010_result_observed"] is False
    assert prereg["baseline"]["paid_provider_call_made_for_w0010"] is False
    assert not (ROOT / "works" / "w0010").exists()
    assert {batch["input_manifest_hash"] for batch in budget["batches"]} == {
        PREREG_SHA256
    }


def test_closing_reserve_is_derived_from_complete_l7_slot_coverage() -> None:
    raw = _load(RUN_BUDGET)
    plan = RunBudgetPlan.from_manifest(raw, work_id="w0010")

    assert plan.cap_amount == pytest.approx(9.0)
    assert dict(plan.pool_limits) == pytest.approx(
        {"player": 3.5, "held_out": 2.6392, "closing": 2.8608}
    )
    assert plan.closing_reserve == pytest.approx(2.8608)
    assert [slot.slot_id for slot in plan.closing_slots] == [
        "title",
        "publication-intent",
        "shelf-comparison",
        "final-projection",
    ]
    assert [slot.max_amount for slot in plan.closing_slots] == pytest.approx(
        [0.8224, 1.1392, 0.8992, 0.0]
    )
    closing = plan.batch_for("L7", "author_primary")
    assert closing.max_amount == pytest.approx(plan.closing_reserve)
    assert closing.expected_slots == tuple(slot.slot_id for slot in plan.closing_slots)


def test_closing_external_slots_fix_current_author_pricing_identity() -> None:
    raw = _load(RUN_BUDGET)
    external = [slot for slot in raw["closing_slots"] if slot["kind"] == "external"]

    assert len(external) == 3
    assert {slot["provider"] for slot in external} == {"anthropic"}
    assert {slot["model"] for slot in external} == {"claude-fable-5"}
    assert {
        slot["pricing_version"] for slot in external
    } == {
        "config/models.yaml@sha256:"
        "c3388c01bbc7f89ce5e051f98add74c5c026777cd1e9b1e3e12c9f3593a7b9c1"
        "#roles.author_primary.pricing"
    }
    for slot in external:
        axes = {axis["name"]: axis for axis in slot["axes"]}
        assert axes["input_tokens"]["usd_per_unit"] == pytest.approx(10.0 / 1_000_000)
        assert axes["output_tokens"]["usd_per_unit"] == pytest.approx(50.0 / 1_000_000)
