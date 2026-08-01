from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from aleph.core.budget import Budget
from aleph.core.config import load_config
from aleph.core.llm import CallLogger, LLMResponse, Message, Router, Usage
from aleph.meta.publication_shadow import (
    PublicationShadow,
    PublicationShadowError,
    ShadowCall,
    ShadowRequest,
)
from scripts import run_w0009_publication_shadow as runner


ROOT = Path(__file__).resolve().parents[1]


class FakeAdapter:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)
        self.requests: list[ShadowRequest] = []
        self.reserved = False
        self.settled = False

    def reserve(self, shadow: PublicationShadow) -> str:
        self.reserved = True
        assert shadow.reserve_usd == pytest.approx(3.9968)
        return "reservation-1"

    def call(self, request: ShadowRequest, *, reservation_id: str) -> ShadowCall:
        assert reservation_id == "reservation-1"
        self.requests.append(request)
        text = next(self.responses)
        return ShadowCall(
            text=text,
            provider="fake",
            model="claude-fable-5",
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=0.001,
            latency_ms=1.0,
            response_hash="ignored",
        )

    def settle(self, reservation_id: str) -> dict:
        assert reservation_id == "reservation-1"
        self.settled = True
        return {"status": "settled", "charged": 0.002, "released": 3.9948}


def _copy_preregistered_fixture(
    tmp_path: Path, *, restore_july_caps: bool = False
) -> PublicationShadow:
    for relative in (
        "works/w0009/publication_shadow/preregistration.json",
        "works/w0009/drafts/v2.md",
        "works/w0009/reviews/trajectory.jsonl",
        "works/w0009/checkpoint.json",
        "works/w0009/decisions.jsonl",
        "works/w0009/calls.jsonl",
        "config/models.yaml",
        "config/budgets.yaml",
        "config/policies.yaml",
        "config/publish.yaml",
        "aleph/meta/publication_gate.py",
    ):
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    for meta in sorted((ROOT / "works").glob("*/final/meta.json")):
        target = tmp_path / meta.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(meta.read_bytes())
    if restore_july_caps:
        config = tmp_path / "config/budgets.yaml"
        text = config.read_text(encoding="utf-8")
        text = text.replace("usd_per_month: 45.0", "usd_per_month: 71.0")
        text = text.replace("max_per_month: 4", "max_per_month: 999")
        config.write_text(text, encoding="utf-8")
    return PublicationShadow.open(tmp_path)


def _enable_august_caps(root: Path) -> None:
    config = root / "config/budgets.yaml"
    text = config.read_text(encoding="utf-8")
    text = text.replace("usd_per_month: 71.0", "usd_per_month: 45.0")
    text = text.replace("max_per_month: 999", "max_per_month: 4")
    config.write_text(text, encoding="utf-8")


def test_preregistration_reconstructs_all_frozen_identities():
    shadow = PublicationShadow.open(ROOT)

    report = shadow.verify()

    assert report["status"] == "VERIFIED_NOT_RUN"
    assert report["packet_count"] == 2
    assert report["reserve_usd"] == pytest.approx(3.9968)


def test_execution_is_blocked_until_date_and_cap_actions(tmp_path):
    shadow = _copy_preregistered_fixture(tmp_path, restore_july_caps=True)

    assert shadow.execution_blockers(today=date(2026, 7, 30)) == (
        "earliest run date has not arrived",
        "monthly API cap is not the preregistered 45 USD",
        "publish.max_per_month is not the preregistered value 4",
    )
    _enable_august_caps(tmp_path)
    assert shadow.execution_blockers(today=date(2026, 8, 1)) == ()


def test_shadow_calls_each_intent_once_and_only_triggers_comparison_for_publish(tmp_path):
    shadow = _copy_preregistered_fixture(tmp_path)
    _enable_august_caps(tmp_path)
    adapter = FakeAdapter(
        [
            '{"publish": false, "reason": "棚に置く"}',
            '{"publish": true, "reason": "公開する"}',
            "棚との差を論じる",
        ]
    )

    result = shadow.run(
        adapter,
        output_dir=tmp_path / "results",
        today=date(2026, 8, 1),
    )

    assert result["status"] == "COMPLETE_AWAITING_BLIND_ANALYSIS"
    assert adapter.reserved and adapter.settled
    assert json.loads((tmp_path / "results/attempt.json").read_text())[
        "attempts_per_slot"
    ] == 1
    assert [request.phase for request in adapter.requests] == [
        "intent",
        "intent",
        "shelf_comparison",
    ]
    assert [row["decision"] for row in result["observations"]] == ["SHELVE", "PUBLISH"]
    assert result["observations"][0]["shelf_comparison"]["status"] == "NOT_TRIGGERED"
    assert (
        result["observations"][1]["shelf_comparison"]["status"]
        == "RECORDED_UNSCORED"
    )
    assert not (tmp_path / "works/w0009/final").exists()
    assert json.loads((tmp_path / "results/observations.json").read_text())["selection"] == (
        "PENDING_BLIND_MIDDLE_ANNOTATION"
    )
    assert result["totals"] == {
        "calls": 3,
        "prompt_tokens": 30,
        "completion_tokens": 15,
        "total_tokens": 45,
        "cost_usd": 0.003,
        "latency_ms": 3.0,
    }
    blind = json.loads(
        (tmp_path / "results/blind_middle_annotation_packet.json").read_text()
    )
    assert blind["mapping_disclosed"] is False
    assert [item["packet_id"] for item in blind["items"]] == [
        "packet-db058b2776b4",
        "packet-be6c78477dfd",
    ]
    assert all("body" not in item for item in blind["items"])


def test_both_primary_intents_finish_before_conditional_comparisons(tmp_path):
    shadow = _copy_preregistered_fixture(tmp_path)
    _enable_august_caps(tmp_path)
    adapter = FakeAdapter(
        [
            '{"publish": true, "reason": "一"}',
            '{"publish": true, "reason": "二"}',
            "棚比較一",
            "棚比較二",
        ]
    )

    shadow.run(
        adapter,
        output_dir=tmp_path / "results",
        today=date(2026, 8, 1),
    )

    assert [request.phase for request in adapter.requests] == [
        "intent",
        "intent",
        "shelf_comparison",
        "shelf_comparison",
    ]


def test_shadow_does_not_use_production_prose_fallback(tmp_path):
    shadow = _copy_preregistered_fixture(tmp_path)
    _enable_august_caps(tmp_path)
    adapter = FakeAdapter(
        [
            "この作品は公開するに値する。",
            '{"publish": false, "reason": "非公開"}',
        ]
    )

    result = shadow.run(
        adapter,
        output_dir=tmp_path / "results",
        today=date(2026, 8, 1),
    )

    first = result["observations"][0]
    assert first["parser"]["classification"] == "NO_JSON"
    assert first["decision"] == "PARSE_INCOMPLETE"
    assert len(adapter.requests) == 2


def test_manifest_drift_fails_before_adapter_reservation(tmp_path):
    shadow = _copy_preregistered_fixture(tmp_path)
    source = tmp_path / "works/w0009/drafts/v2.md"
    source.write_text(source.read_text(encoding="utf-8") + "drift", encoding="utf-8")
    adapter = FakeAdapter([])

    with pytest.raises(PublicationShadowError, match="full stimulus identity drift"):
        shadow.run(adapter, output_dir=tmp_path / "results", today=date(2026, 8, 1))

    assert not adapter.reserved


def test_existing_result_path_blocks_duplicate_paid_attempt(tmp_path):
    shadow = _copy_preregistered_fixture(tmp_path)
    _enable_august_caps(tmp_path)
    output = tmp_path / "results"
    output.mkdir()
    adapter = FakeAdapter([])

    with pytest.raises(PublicationShadowError, match="already exists"):
        shadow.run(adapter, output_dir=output, today=date(2026, 8, 1))

    assert not adapter.reserved


def test_budget_reservation_uses_separate_shadow_work_identity(tmp_path):
    shadow = _copy_preregistered_fixture(tmp_path)
    _enable_august_caps(tmp_path)
    config = load_config(tmp_path)
    state = tmp_path / "state/budget.json"
    existing = Budget(config, state_path=state)
    existing.charge("api", 8.9, work_id="w0009")
    adapter = runner.BudgetRouterAdapter(shadow, tmp_path / "results")

    reservation_id = adapter.reserve(shadow)

    assert adapter.budget.work_remaining("w0009") == pytest.approx(0.1)
    assert adapter.budget.work_remaining(runner.SHADOW_WORK_ID) == pytest.approx(
        9.0 - 3.9968
    )
    settlement = adapter.settle(reservation_id)
    assert settlement["status"] == "settled"


def test_audit_gate_binds_clean_head_commit_tree_and_terminal_pass(tmp_path, monkeypatch):
    commit = "a" * 40
    head = "c" * 40
    tree = "b" * 40
    report = tmp_path / "audit.md"
    report.write_text(
        f"candidate commit: {commit}\ncandidate tree: {tree}\n\nVERDICT: PASS\n",
        encoding="utf-8",
    )

    def fake_git(*args):
        if args == ("status", "--porcelain"):
            return ""
        if args == ("rev-parse", "HEAD"):
            return head
        if args == ("rev-parse", commit):
            return commit
        if args == ("rev-parse", f"{commit}^{{tree}}"):
            return tree
        if args == ("merge-base", "--is-ancestor", commit, head):
            return ""
        if args == ("diff", "--name-only", f"{commit}..{head}"):
            return (
                "config/budgets.yaml\nPROGRESS.md\n"
                "reports/W0009_PUBLICATION_SHADOW_AUGUST_GATE_REAUDIT_20260801.md"
            )
        raise AssertionError(args)

    monkeypatch.setattr(runner, "_git", fake_git)

    evidence = runner.verify_audit_gate(report, commit)

    assert evidence["candidate_commit"] == commit
    assert evidence["candidate_tree"] == tree
    assert evidence["current_head"] == head


def test_audit_gate_rejects_post_audit_code_change(tmp_path, monkeypatch):
    commit = "a" * 40
    head = "c" * 40
    tree = "b" * 40
    report = tmp_path / "audit.md"
    report.write_text(
        f"candidate commit: {commit}\ncandidate tree: {tree}\n\nVERDICT: PASS\n",
        encoding="utf-8",
    )

    def fake_git(*args):
        values = {
            ("status", "--porcelain"): "",
            ("rev-parse", "HEAD"): head,
            ("rev-parse", commit): commit,
            ("rev-parse", f"{commit}^{{tree}}"): tree,
            ("merge-base", "--is-ancestor", commit, head): "",
            ("diff", "--name-only", f"{commit}..{head}"): "aleph/core/llm.py",
        }
        return values[args]

    monkeypatch.setattr(runner, "_git", fake_git)

    with pytest.raises(PublicationShadowError, match="outside the execution allowlist"):
        runner.verify_audit_gate(report, commit)


def test_router_transport_retries_can_be_disabled(tmp_path):
    config = load_config(ROOT)
    config.models["roles"]["retry_test"] = {
        "provider": "anthropic",
        "model": "fake",
        "max_tokens": 1,
        "pricing": {"input_per_mtok": 0.0, "output_per_mtok": 0.0},
    }
    router = Router(config, CallLogger(tmp_path / "calls.jsonl"), Budget(config))

    class FailingProvider:
        name = "fake"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, model, messages, **kwargs):
            self.calls += 1
            raise RuntimeError("transport")

    provider = FailingProvider()
    router._provider_for_test = provider

    with pytest.raises(RuntimeError, match="transport"):
        router.call(
            "retry_test",
            [Message("user", "x")],
            transport_retries=0,
        )

    assert provider.calls == 1


@pytest.mark.parametrize("invalid", [True, -1, 0.5, "0"])
def test_router_rejects_invalid_transport_retry_contract_before_provider(
    tmp_path, invalid
):
    config = load_config(ROOT)
    config.models["roles"]["retry_test"] = {
        "provider": "anthropic",
        "model": "fake",
        "max_tokens": 1,
        "pricing": {"input_per_mtok": 0.0, "output_per_mtok": 0.0},
    }
    router = Router(config, CallLogger(tmp_path / "calls.jsonl"), Budget(config))

    class Provider:
        name = "fake"
        calls = 0

        def complete(self, model, messages, **kwargs):
            self.calls += 1
            return LLMResponse("ok", model, "fake", Usage(1, 1), 0.0)

    provider = Provider()
    router._provider_for_test = provider

    with pytest.raises(ValueError, match="transport_retries"):
        router.call(
            "retry_test",
            [Message("user", "x")],
            transport_retries=invalid,
        )

    assert provider.calls == 0


def test_router_default_transport_retry_count_is_preserved(tmp_path, monkeypatch):
    config = load_config(ROOT)
    config.models["roles"]["retry_test"] = {
        "provider": "anthropic",
        "model": "fake",
        "max_tokens": 1,
        "pricing": {"input_per_mtok": 0.0, "output_per_mtok": 0.0},
    }
    router = Router(config, CallLogger(tmp_path / "calls.jsonl"), Budget(config))

    class EventuallySuccessfulProvider:
        name = "fake"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, model, messages, **kwargs):
            self.calls += 1
            if self.calls < 3:
                raise RuntimeError("transport")
            return LLMResponse("ok", model, "fake", Usage(1, 1), 0.0)

    provider = EventuallySuccessfulProvider()
    router._provider_for_test = provider
    monkeypatch.setattr("aleph.core.llm.time.sleep", lambda _: None)

    response = router.call("retry_test", [Message("user", "x")])

    assert response.text == "ok"
    assert provider.calls == 3
    record = json.loads((tmp_path / "calls.jsonl").read_text())
    assert record["params"]["transport_retries"] == 2
