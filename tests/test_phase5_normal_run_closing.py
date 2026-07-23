from __future__ import annotations

import json
from pathlib import Path

import pytest

from aleph.core.artifacts import Work
from aleph.core.budget import BatchLookupError, Budget, BudgetExceeded, RunBudgetPlan
from aleph.core.config import load_config
from aleph.core.llm import CallLogger, LLMResponse, Message, Router, Usage
from aleph.core.loop import State
from aleph.pipeline import RealDeps, run_work


ROOT = Path(__file__).resolve().parents[1]
_HASH = "b" * 64


def _batch(batch_id, pool, role, amount, phases):
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


def _manifest(*, closing=0.6):
    return {
        "version": 1,
        "cap_amount": 2.0 + closing,
        "pools": {"player": 1.0, "held_out": 1.0, "closing": closing},
        "batches": [
            _batch("player-author", "player", "author_primary", 1.0, ["L1", "L4-L5"]),
            _batch("heldout-jury", "held_out", "critic_jury", 1.0, ["L6"]),
            _batch("closing-author", "closing", "author_primary", closing, ["L7"]),
        ],
    }


def _real_deps(tmp_path, *, manifest=None):
    config = load_config(ROOT)
    work = Work(tmp_path / "works", "w-run")
    work.create({"run_budget": manifest or _manifest()})
    budget = Budget(config, state_path=tmp_path / "budget.json")
    router = Router(config, CallLogger(work.calls), budget)
    deps = RealDeps(
        work,
        router,
        config=config,
        index_dir=tmp_path / "atlas",
        search_fn=lambda *args, **kwargs: [],
        poetics_dir=tmp_path / "poetics",
    )
    return work, budget, router, deps


def test_run_admission_is_all_or_nothing_before_the_first_transition(tmp_path):
    config = load_config(ROOT)
    budget = Budget(config, state_path=tmp_path / "budget.json")
    plan = RunBudgetPlan.from_manifest(_manifest(closing=1.0), work_id="w-run")
    budget.charge("api", config.budgets["api"]["usd_per_month"] - 2.5)

    with pytest.raises(BudgetExceeded):
        budget.admit_run_plan(plan)

    assert budget.status()["reservations"]["active_count"] == 0
    assert budget.scope_remaining("run:w-run") is None


def test_real_deps_routes_api_calls_to_the_phase_role_reservation(tmp_path):
    work, budget, router, deps = _real_deps(tmp_path)
    reservations = deps.begin_run_budget()

    class Provider:
        name = "fake"

        def complete(self, model, messages, **kwargs):
            return LLMResponse("ok", model, "fake", Usage(1, 1), 0.1)

    router._provider_for_test = Provider()
    deps._phase = "L7"
    router.call(
        "author_primary",
        [Message("user", "close")],
        **deps._call_overrides("author_primary"),
        max_tokens=10,
    )

    call = json.loads(work.calls.read_text(encoding="utf-8"))
    closing_id = reservations["closing-author"].id
    assert call["reservation_id"] == closing_id
    assert call["charged_to"] == "run:w-run"
    assert call["phase"] == "L7"
    assert budget.reservation_remaining(closing_id) == pytest.approx(
        _manifest()["pools"]["closing"] - call["cost_usd"]
    )


def test_unregistered_api_phase_role_fails_before_provider_call(tmp_path):
    _, _, router, deps = _real_deps(tmp_path)
    deps.begin_run_budget()

    class Provider:
        name = "forbidden"

        def complete(self, model, messages, **kwargs):
            raise AssertionError("provider must not run without a registered route")

    router._provider_for_test = Provider()
    deps._phase = "L6"
    with pytest.raises(BatchLookupError, match="no batch covers"):
        deps._author("unregistered author call")


def test_protected_run_defers_unmanifested_l8_reflection_without_call(tmp_path):
    work, _, router, deps = _real_deps(tmp_path)

    class Provider:
        name = "forbidden"

        def complete(self, model, messages, **kwargs):
            raise AssertionError("L8 is outside the protected run manifest")

    router._provider_for_test = Provider()
    result = deps.reflect_poetics(work)

    assert result["applied"] is False
    assert "L8" in result["diff_reason"]


class _ClosingDeps:
    def __init__(self, budget, plan, *, lose_closing=False):
        self.budget = budget
        self.plan = plan
        self.lose_closing = lose_closing
        self.reservations = {}
        self.begin_calls = 0
        self.finish_calls = 0

    def begin_run_budget(self):
        self.begin_calls += 1
        self.reservations = self.budget.admit_run_plan(self.plan)
        return self.reservations

    def closing_available(self):
        reservation = self.reservations["closing-author"]
        if self.lose_closing and self.budget.reservation_status(reservation.id) == "active":
            self.budget.settle_batch(reservation.id, command_id="fixture-lost-closing")
        return self.budget.reservation_status(reservation.id) == "active"

    def run_completion_category(self, stop_path):
        if not self.closing_available():
            return "resource_interrupted"
        return "complete_short" if stop_path in {"budget", "guard_limit"} else "complete"

    def finish_run_budget(self, *, stop_path, terminal_state):
        self.finish_calls += 1
        category = self.run_completion_category(stop_path)
        for reservation in self.reservations.values():
            if self.budget.reservation_status(reservation.id) == "active":
                self.budget.settle_batch(
                    reservation.id,
                    command_id=f"run:w-run:settle:{reservation.spec['batch_id']}",
                )
        return category

    def choose_intent(self, work):
        return "人間 1.0"

    def explore(self, work):
        return {"description": "fixture"}

    def gather_materials(self, work, niche):
        return []

    def compose_and_draft(self, work, niche, audience, materials):
        work.draft_path(1).write_text("draft", encoding="utf-8")

    def critique_and_revise(self, work, audience):
        trajectory = work.reviews / "trajectory.jsonl"
        trajectory.write_text(
            json.dumps({"version": 1, "mean_score": 7.0, "instructions": []}) + "\n",
            encoding="utf-8",
        )

    def decide_stop(self, work):
        return {"stop": True, "path": "budget", "reason": "player pool exhausted"}

    def decide_publication(self, work, audience):
        return {"decision": "SHELVE", "reason": "著者が非公開を選択した"}


def _closing_fixture(tmp_path, *, lose_closing=False):
    config = load_config(ROOT)
    work = Work(tmp_path / "works", "w-run")
    work.create({"run_budget": _manifest()})
    plan = RunBudgetPlan.from_manifest(_manifest(), work_id=work.work_id)
    budget = Budget(config, state_path=tmp_path / "budget.json")
    deps = _ClosingDeps(budget, plan, lose_closing=lose_closing)
    return work, budget, deps


def test_player_exhaustion_with_live_closing_completes_short_and_settles(tmp_path):
    work, budget, deps = _closing_fixture(tmp_path)

    assert run_work(work, deps, decided_by="fixture") == State.SHELVE

    decisions = [
        json.loads(line) for line in work.decisions.read_text(encoding="utf-8").splitlines()
    ]
    assert any(row["decision"] == "run_completion:complete_short" for row in decisions)
    assert any(row["decision"] == "failure_category:publication_choice" for row in decisions)
    assert budget.status()["reservations"]["active_count"] == 0

    assert run_work(work, deps, decided_by="fixture") == State.SHELVE
    decisions_after_resume = [
        json.loads(line) for line in work.decisions.read_text(encoding="utf-8").splitlines()
    ]
    assert [
        row["decision"]
        for row in decisions_after_resume
        if row["decision"].startswith("run_completion:")
    ] == ["run_completion:complete_short"]


def test_lost_closing_is_resource_interrupted_without_publication_call(tmp_path):
    work, budget, deps = _closing_fixture(tmp_path, lose_closing=True)

    def forbidden(*args, **kwargs):
        raise AssertionError("publication must not run after closing is lost")

    deps.decide_publication = forbidden
    assert run_work(work, deps, decided_by="fixture") == State.SHELVE

    decisions = [
        json.loads(line) for line in work.decisions.read_text(encoding="utf-8").splitlines()
    ]
    assert any(row["decision"] == "run_completion:resource_interrupted" for row in decisions)
    assert any(row["decision"] == "failure_category:resource_stop" for row in decisions)


def test_failed_admission_leaves_work_unstarted(tmp_path):
    work, budget, deps = _closing_fixture(tmp_path)
    budget.charge("api", load_config(ROOT).budgets["api"]["usd_per_month"])

    with pytest.raises(BudgetExceeded):
        run_work(work, deps, decided_by="fixture")

    assert not work.checkpoint.exists()
    assert work.decisions.read_text(encoding="utf-8") == ""
