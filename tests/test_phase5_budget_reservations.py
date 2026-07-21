from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json

import pytest

from aleph.core.budget import (
    BatchSpec,
    Budget,
    BudgetExceeded,
    BudgetUnreconciled,
    ReservationConflict,
)
from aleph.core.config import load_config
from aleph.core.llm import CallContext, CallLogger, LLMResponse, Message, Router, Usage
from aleph.core.artifacts import Work
from aleph.core.experiment import ExperimentRun


ROOT = Path(__file__).resolve().parents[1]


def _budget(tmp_path, *, scope_limit=4.0, player=2.5, held_out=1.0, closing=0.5):
    budget = Budget(load_config(ROOT), state_path=tmp_path / "budget.json")
    budget.register_scope_limit("run:test", ledger="api", limit=scope_limit)
    budget.register_pool_limits(
        "run:test", ledger="api", player=player, held_out=held_out, closing=closing
    )
    return budget


def _spec(*, batch="jury", pool="held_out", amount=1.0):
    return BatchSpec(
        batch_id=batch,
        ledger="api",
        charged_to="run:test",
        pool=pool,
        role="critic_jury",
        max_amount=amount,
        work_id="w-test",
        expected_slots=("juror-1",),
        input_manifest_hash="a" * 64,
    )


def test_reservation_is_durable_idempotent_and_protects_scope_commitment(tmp_path):
    first = _budget(tmp_path)
    reservation = first.reserve_batch(_spec(pool="closing", amount=0.5), command_id="close")

    restarted = Budget(load_config(ROOT), state_path=tmp_path / "budget.json")
    same = restarted.reserve_batch(_spec(pool="closing", amount=0.5), command_id="close")

    assert same.id == reservation.id
    assert restarted.scope_remaining("run:test") == pytest.approx(3.5)
    with pytest.raises(BudgetExceeded):
        restarted.charge("api", 3.6, meta={"charged_to": "run:test"}, work_id="other")


def test_held_out_can_borrow_player_but_reverse_and_closing_borrow_are_rejected(tmp_path):
    budget = _budget(tmp_path, player=2.5, held_out=1.0, closing=0.5)
    held_out = budget.reserve_batch(_spec(amount=1.5), command_id="held-out")
    assert held_out.allocations == {"held_out": 1.0, "player": 0.5}

    with pytest.raises(BudgetExceeded):
        budget.reserve_batch(_spec(batch="player", pool="player", amount=2.1), command_id="player")
    with pytest.raises(BudgetExceeded):
        budget.reserve_batch(_spec(batch="closing", pool="closing", amount=0.6), command_id="closing")


def test_manifest_cannot_override_the_code_owned_borrowing_matrix():
    with pytest.raises(TypeError):
        BatchSpec(
            batch_id="bad",
            ledger="api",
            charged_to="run:test",
            pool="player",
            role="author",
            max_amount=1.0,
            input_manifest_hash="a" * 64,
            allow_borrow_from="closing",  # type: ignore[call-arg]
        )


def test_charge_id_and_settlement_are_idempotent_across_restart(tmp_path):
    budget = _budget(tmp_path)
    reservation = budget.reserve_batch(_spec(), command_id="reserve")
    charge = budget.charge(
        "api",
        0.6,
        meta={"reservation_id": reservation.id, "charge_id": "charge-1"},
        work_id="w-test",
    )
    duplicate = budget.charge(
        "api",
        0.6,
        meta={"reservation_id": reservation.id, "charge_id": "charge-1"},
        work_id="w-test",
    )
    assert duplicate == charge
    assert budget.status()["api"]["spent"] == pytest.approx(0.6)

    settlement = budget.settle_batch(reservation.id, command_id="settle")
    restarted = Budget(load_config(ROOT), state_path=tmp_path / "budget.json")
    assert restarted.settle_batch(reservation.id, command_id="settle") == settlement
    with pytest.raises(ReservationConflict):
        restarted.settle_batch(reservation.id, command_id="different")


def test_completed_overage_is_recorded_unreconciled_and_blocks_next_admission(tmp_path):
    budget = _budget(tmp_path)
    reservation = budget.reserve_batch(_spec(amount=0.5), command_id="reserve")

    event = budget.charge(
        "api",
        0.75,
        meta={"reservation_id": reservation.id, "charge_id": "actual-overage"},
        work_id="w-test",
    )

    assert event["billing_status"] == "unreconciled"
    assert budget.status()["api"]["spent"] == pytest.approx(0.75)
    with pytest.raises(BudgetUnreconciled):
        budget.precheck("api", 0.01)
    with pytest.raises(BudgetUnreconciled):
        budget.settle_batch(reservation.id, command_id="settle")


def test_two_preexisting_budget_instances_cannot_over_admit_same_scope(tmp_path):
    first = _budget(tmp_path, scope_limit=3.0, player=3.0, held_out=0.0, closing=0.0)
    second = Budget(load_config(ROOT), state_path=tmp_path / "budget.json")
    first.reserve_batch(_spec(pool="player", amount=2.0), command_id="first")

    with pytest.raises(BudgetExceeded):
        second.reserve_batch(_spec(batch="second", pool="player", amount=2.0), command_id="second")


def test_reservation_command_collision_rejects_changed_manifest(tmp_path):
    budget = _budget(tmp_path)
    spec = _spec()
    budget.reserve_batch(spec, command_id="same-command")

    with pytest.raises(ReservationConflict):
        budget.reserve_batch(replace(spec, max_amount=0.9), command_id="same-command")


def test_router_consumes_the_matching_reservation_and_logs_its_identity(tmp_path):
    config = load_config(ROOT)
    budget = _budget(tmp_path)
    spec = replace(_spec(pool="player", amount=1.0), role="author_primary")
    reservation = budget.reserve_batch(spec, command_id="author-batch")
    logger = CallLogger(tmp_path / "calls.jsonl")
    router = Router(config, logger, budget)

    class Provider:
        name = "fake"

        def complete(self, model, messages, **kwargs):
            return LLMResponse("ok", model, "fake", Usage(1, 1), 0.2)

    router._provider_for_test = Provider()
    context = CallContext(
        command_id="author-slot-1",
        work_id="w-test",
        experiment_id="exp-test",
        phase="author",
        arm="canonical",
        charged_to="run:test",
        reservation_id=reservation.id,
    )

    router.call("author_primary", [Message("user", "write")], call_context=context)

    call = json.loads((tmp_path / "calls.jsonl").read_text(encoding="utf-8"))
    assert call["reservation_id"] == reservation.id
    assert call["billing_status"] == "charged"
    assert budget.status()["api"]["committed"] == pytest.approx(1.0 - call["cost_usd"])


def test_experiment_manifest_registers_fixed_pool_amounts_without_a_borrowing_dsl(tmp_path):
    work = Work(tmp_path / "works", "w-budget-manifest")
    work.create(
        {
            "experiment": {
                "id": "pool-test",
                "hypothesis": "fixture",
                "intervention": "a",
                "control": "b",
                "observations": ["cost"],
                "budget_cap_usd": 4.0,
                "protected_pools": {"player": 2.5, "held_out": 1.0, "closing": 0.5},
            }
        }
    )
    run = ExperimentRun.open(work.dir)
    budget = Budget(load_config(ROOT), state_path=tmp_path / "manifest-budget.json")

    run.bind_budget(budget)
    reservation = budget.reserve_batch(
        replace(_spec(), charged_to="experiment:pool-test"), command_id="manifest-held-out"
    )

    assert reservation.allocations == {"held_out": 1.0}
