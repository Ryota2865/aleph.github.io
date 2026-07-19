from __future__ import annotations

import json
from dataclasses import replace

import pytest

from aleph.core.artifacts import Work
from aleph.core.budget import Budget, BudgetExceeded
from aleph.core.config import load_config
from aleph.core.evaluation import EvaluationPacket, EvaluationPacketError
from aleph.core.experiment import ExperimentRun
from aleph.core.llm import CallLogger, LLMResponse, Message, ProvenanceError, Router, Usage
from aleph.core.work_snapshot import WorkReader
from aleph.critique.review import run_review

pytestmark = pytest.mark.m6

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


class CountingProvider:
    name = "fake"

    def __init__(self):
        self.calls = 0

    def complete(self, model, messages, **kwargs):
        self.calls += 1
        return LLMResponse(
            text="ok",
            model=model,
            provider=self.name,
            usage=Usage(prompt_tokens=1, completion_tokens=1),
            cost_usd=0.0,
        )


def test_revoked_constraint_is_not_an_l6_penalty(tmp_path):
    work = Work(tmp_path / "works", "w9003")
    work.create(
        {
            "experiment": {
                "id": "exp-revoke",
                "constraints": [
                    {
                        "id": "period-style",
                        "text": "大正時代の文体を使う",
                        "source": "critic",
                        "scope": ["L4", "L5", "L6", "L7"],
                        "priority": 10,
                    }
                ],
                "amendments": [
                    {
                        "id": "release-period-style",
                        "action": "revoke",
                        "target": "period-style",
                        "source": "owner-approved experiment amendment",
                        "scope": ["L4", "L5", "L6", "L7"],
                        "priority": 20,
                    }
                ],
            }
        }
    )
    work.intent.write_text("# Intent\n\n人間 1.0", encoding="utf-8")
    (work.compositions / "criteria.md").write_text("作品固有の基準", encoding="utf-8")
    work.draft_path(1).write_text("原稿", encoding="utf-8")

    snapshot = WorkReader(work.dir).snapshot()
    packet = EvaluationPacket.for_draft(snapshot, 1)

    assert snapshot.effective_constraints == ()
    assert packet.effective_constraints == ()
    assert packet.revoked_constraints == ("大正時代の文体を使う",)
    rendered = packet.render_for("L6")
    assert "大正時代の文体を使う" in rendered
    assert "減点してはならない" in rendered
    assert packet.hash == packet.recompute_hash()


def test_incomplete_experiment_call_provenance_fails_before_provider(tmp_path, monkeypatch):
    config = load_config(ROOT)
    provider = CountingProvider()
    router = Router(config, CallLogger(tmp_path / "calls.jsonl"), Budget(config))
    monkeypatch.setattr(router, "_provider_for_test", provider, raising=False)

    with pytest.raises(ProvenanceError, match="command_id.*arm.*charged_to"):
        router.call(
            "scout",
            [Message("user", "test")],
            work_id="w9003",
            experiment_id="exp-revoke",
            phase="L4",
        )

    assert provider.calls == 0
    assert not (tmp_path / "calls.jsonl").exists()


def test_complete_experiment_call_links_call_and_charge_events(tmp_path, monkeypatch):
    config = load_config(ROOT)
    provider = CountingProvider()
    budget_path = tmp_path / "budget.json"
    router = Router(
        config,
        CallLogger(tmp_path / "calls.jsonl"),
        Budget(config, state_path=budget_path),
    )
    monkeypatch.setattr(router, "_provider_for_test", provider, raising=False)

    router.call(
        "scout",
        [Message("user", "test")],
        command_id="exp-revoke:L4:compose",
        work_id="w9003",
        experiment_id="exp-revoke",
        phase="L4",
        arm="control",
        charged_to="experiment:exp-revoke",
    )

    call = json.loads((tmp_path / "calls.jsonl").read_text(encoding="utf-8"))
    ledger = json.loads(budget_path.read_text(encoding="utf-8"))
    charge = ledger["charge_events"][0]
    assert call["call_id"]
    assert call["charge_id"] == charge["charge_id"]
    for field in ("command_id", "work_id", "experiment_id", "phase", "arm", "charged_to"):
        assert charge[field] == call[field]
    assert charge["call_id"] == call["call_id"]


def test_blind_selector_cannot_observe_arm_identity_or_jury_data(tmp_path):
    work = Work(tmp_path / "works", "w9004")
    work.create(
        {
            "experiment": {
                "id": "exp-blind",
                "version": 1,
                "hypothesis": "arm changes the draft",
                "intervention": "remove material",
                "control": "retain material",
                "observations": ["draft quality"],
                "budget_cap_usd": 2.0,
                "blind": {"seed": 42},
            }
        }
    )
    run = ExperimentRun.open(work.dir)
    observed = ""

    def selector(candidates):
        nonlocal observed
        observed = repr(candidates)
        assert {candidate.label for candidate in candidates} == {"A", "B"}
        assert all(candidate.technical_floor == {"pass": True} for candidate in candidates)
        return {"choice": "A", "rationale": "stronger draft"}

    selection = run.select_blind(
        {
            "control": {"text": "FIRST_BODY", "technical_floor": {"pass": True}},
            "intervention": {"text": "SECOND_BODY", "technical_floor": {"pass": True}},
        },
        selector=selector,
        decided_by="author-test",
    )

    assert "control" not in observed.lower()
    assert "intervention" not in observed.lower()
    assert "jury" not in observed.lower()
    assert selection.chosen_arm in {"control", "intervention"}
    event = run.events()[-1]
    assert event["type"] == "blind_selection"
    assert event["label_mapping"]


def test_jury_reveal_before_blind_selection_fails_closed(tmp_path):
    work = Work(tmp_path / "works", "w9005")
    work.create(
        {
            "experiment": {
                "id": "exp-order",
                "version": 1,
                "hypothesis": "order matters",
                "intervention": "x",
                "control": "y",
                "observations": ["selection"],
                "budget_cap_usd": 2.0,
            }
        }
    )
    run = ExperimentRun.open(work.dir)

    with pytest.raises(Exception, match="blind selection"):
        run.reveal_jury(
            [{"arm": "control", "scores": [8.0]}],
            decided_by="jury-test",
        )

    assert run.events() == []


def test_experiment_cap_includes_select_and_canonical_l6(tmp_path, monkeypatch):
    work = Work(tmp_path / "works", "w9006")
    work.create(
        {
            "experiment": {
                "id": "exp-cap",
                "version": 1,
                "hypothesis": "all phases fit one cap",
                "intervention": "x",
                "control": "y",
                "observations": ["cost"],
                "budget_cap_usd": 2.0,
            }
        }
    )
    config = load_config(ROOT)
    config.models["roles"]["_phase3_api"] = {
        "provider": "anthropic",
        "model": "fake",
        "max_tokens": 1000,
        "pricing": {"input_per_mtok": 0.0, "output_per_mtok": 1000.0},
    }
    budget = Budget(config, state_path=tmp_path / "budget.json")
    run = ExperimentRun.open(work.dir)
    run.bind_budget(budget)
    budget.charge(
        "api",
        1.2,
        meta={
            "call_id": "select-call",
            "command_id": "select",
            "work_id": work.work_id,
            "experiment_id": run.experiment_id,
            "phase": "select",
            "arm": "main",
            "charged_to": "experiment:exp-cap",
        },
        work_id=work.work_id,
    )
    provider = CountingProvider()
    router = Router(config, CallLogger(tmp_path / "calls.jsonl"), budget)
    monkeypatch.setattr(router, "_provider_for_test", provider, raising=False)

    with pytest.raises(BudgetExceeded, match="experiment:exp-cap"):
        router.call(
            "_phase3_api",
            [Message("user", "canonical review")],
            command_id="canonical-l6",
            work_id=work.work_id,
            experiment_id=run.experiment_id,
            phase="canonical-L6",
            arm="main",
            charged_to="experiment:exp-cap",
        )

    assert provider.calls == 0


def test_l6_rejects_packet_hash_disagreement_before_reviewers(tmp_path):
    work = Work(tmp_path / "works", "w9007")
    work.create(
        {
            "experiment": {
                "id": "exp-packet",
                "criteria_constraints": "active constraint",
            }
        }
    )
    work.intent.write_text("人間 1.0", encoding="utf-8")
    (work.compositions / "criteria.md").write_text("criteria", encoding="utf-8")
    work.draft_path(1).write_text("draft", encoding="utf-8")
    packet = EvaluationPacket.for_draft(WorkReader(work.dir).snapshot(), 1)
    corrupt = replace(packet, packet_hash="0" * 64)
    calls = 0

    def forbidden(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("review adapter must not run")

    with pytest.raises(EvaluationPacketError, match="hash"):
        run_review(
            work,
            "draft",
            "criteria",
            "人間 1.0",
            version=1,
            scout=forbidden,
            jury=[forbidden],
            reader=forbidden,
            embedder=forbidden,
            index_dir=tmp_path,
            search_fn=forbidden,
            packet=corrupt,
        )

    assert calls == 0


def test_experiment_reconciliation_matches_calls_ledger_and_provider(tmp_path):
    work = Work(tmp_path / "works", "w9008")
    work.create(
        {
            "experiment": {
                "id": "exp-reconcile",
                "hypothesis": "costs match",
                "intervention": "x",
                "control": "y",
                "observations": ["cost"],
                "budget_cap_usd": 2.0,
            }
        }
    )
    run = ExperimentRun.open(work.dir)
    call = {
        "call_id": "call-1",
        "charge_id": "charge-1",
        "command_id": "compose",
        "work_id": work.work_id,
        "experiment_id": run.experiment_id,
        "phase": "L4",
        "arm": "control",
        "charged_to": "experiment:exp-reconcile",
        "cost_usd": 0.75,
    }
    calls_path = tmp_path / "calls.jsonl"
    calls_path.write_text(json.dumps(call) + "\n", encoding="utf-8")
    charge = {
        **{key: call[key] for key in ("call_id", "command_id", "work_id", "experiment_id", "phase", "arm", "charged_to")},
        "charge_id": "charge-1",
        "ledger": "api",
        "amount": 0.75,
    }
    provider = {
        "call_id": "call-1",
        "charged_to": "experiment:exp-reconcile",
        "amount_usd": 0.75,
    }

    report = run.reconcile(
        calls_path=calls_path,
        charge_events=[charge],
        provider_charges=[provider],
    )

    assert report["status"] == "matched"
    assert report["calls"]["total_usd"] == pytest.approx(0.75)
    assert report["ledger"]["total_usd"] == pytest.approx(0.75)
    assert report["provider"]["total_usd"] == pytest.approx(0.75)
    assert report["issues"] == []


def test_reconciliation_missing_provenance_is_unreconciled(tmp_path):
    work = Work(tmp_path / "works", "w9009")
    work.create(
        {
            "experiment": {
                "id": "exp-legacy",
                "hypothesis": "legacy evidence remains incomplete",
                "intervention": "x",
                "control": "y",
                "observations": ["cost"],
                "budget_cap_usd": 2.0,
            }
        }
    )
    run = ExperimentRun.open(work.dir)
    calls_path = tmp_path / "calls.jsonl"
    calls_path.write_text(json.dumps({"cost_usd": 0.75}) + "\n", encoding="utf-8")

    report = run.reconcile(
        calls_path=calls_path,
        charge_events=[],
        provider_charges=[],
    )

    assert report["status"] == "unreconciled"
    assert any("missing provenance" in issue for issue in report["issues"])
