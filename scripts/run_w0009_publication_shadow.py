"""Verify or execute the preregistered w0009 publication-input shadow.

Verification is read-only and is the default safe operation. Paid execution
requires explicit flags plus a clean audited candidate identity.
"""
from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path
from typing import Any

from aleph.core.budget import BatchSpec, Budget
from aleph.core.config import load_config
from aleph.core.llm import CallContext, CallLogger, Message, Router
from aleph.meta.publication_shadow import (
    PublicationShadow,
    PublicationShadowError,
    ShadowCall,
    ShadowRequest,
)


ROOT = Path(__file__).resolve().parents[1]
SHADOW_WORK_ID = "w0009-publication-shadow"
POST_AUDIT_ALLOWED_PATHS = frozenset(
    {
        "PLAN_CHANGELOG.md",
        "PROGRESS.md",
        "README.en.md",
        "README.md",
        "config/budgets.yaml",
        "config/formal-audits.json",
        "designs/next-designer-execution-plan.md",
        "reports/W0009_PUBLICATION_SHADOW_RUNNER_AUDIT_20260730.md",
    }
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def verify_audit_gate(report: Path, candidate_commit: str) -> dict[str, Any]:
    report = Path(report)
    text = report.read_text(encoding="utf-8")
    nonempty = [line.strip() for line in text.splitlines() if line.strip()]
    if not nonempty or nonempty[-1] != "VERDICT: PASS":
        raise PublicationShadowError("audit report does not end with VERDICT: PASS")
    head = _git("rev-parse", "HEAD")
    commit = _git("rev-parse", candidate_commit)
    tree = _git("rev-parse", f"{commit}^{{tree}}")
    if _git("status", "--porcelain"):
        raise PublicationShadowError("paid execution requires a clean audited candidate")
    if commit not in text or tree not in text:
        raise PublicationShadowError("audit report does not bind the candidate commit and tree")
    try:
        _git("merge-base", "--is-ancestor", commit, head)
    except subprocess.CalledProcessError as exc:
        raise PublicationShadowError(
            "current HEAD does not descend from the audited candidate"
        ) from exc
    changed = tuple(
        path
        for path in _git("diff", "--name-only", f"{commit}..{head}").splitlines()
        if path
    )
    unexpected = sorted(set(changed) - POST_AUDIT_ALLOWED_PATHS)
    if unexpected:
        raise PublicationShadowError(
            "post-audit changes are outside the execution allowlist: "
            + ", ".join(unexpected)
        )
    return {
        "candidate_commit": commit,
        "candidate_tree": tree,
        "current_head": head,
        "post_audit_paths": list(changed),
        "audit_report": str(report),
    }


class BudgetRouterAdapter:
    def __init__(self, shadow: PublicationShadow, output_dir: Path) -> None:
        self.shadow = shadow
        self.config = load_config(shadow.root)
        self.budget = Budget(self.config, state_path=shadow.root / "state/budget.json")
        self.router = Router(
            self.config,
            CallLogger(output_dir / "calls.jsonl", secrets=self.config.secrets.values()),
            self.budget,
        )

    def reserve(self, shadow: PublicationShadow) -> str:
        self.budget.register_scope_limit(
            shadow.charged_to,
            ledger="api",
            limit=shadow.reserve_usd,
        )
        self.budget.register_pool_limits(
            shadow.charged_to,
            ledger="api",
            player=0.0,
            held_out=0.0,
            closing=shadow.reserve_usd,
        )
        spec = BatchSpec(
            batch_id="w0009-publication-input-shadow",
            ledger="api",
            charged_to=shadow.charged_to,
            pool="closing",
            role=str(shadow.manifest["model"]["role"]),
            max_amount=shadow.reserve_usd,
            work_id=SHADOW_WORK_ID,
            expected_slots=shadow.expected_slots,
            phases=("intent", "shelf_comparison"),
            input_manifest_hash=shadow.manifest_sha256,
            semantic_retries=0,
            atomic_projection=True,
            protected_definition_version="w0009-publication-shadow-v1",
        )
        reservation = self.budget.reserve_batch(
            spec,
            command_id=f"{shadow.charged_to}:reserve",
        )
        return reservation.id

    def call(self, request: ShadowRequest, *, reservation_id: str) -> ShadowCall:
        started = time.monotonic()
        response = self.router.call(
            str(self.shadow.manifest["model"]["role"]),
            [Message("user", request.prompt)],
            transport_retries=0,
            call_context=CallContext(
                command_id=f"{self.shadow.charged_to}:{request.slot}",
                work_id=SHADOW_WORK_ID,
                experiment_id=self.shadow.experiment_id,
                phase=request.phase,
                arm=request.packet_id,
                charged_to=self.shadow.charged_to,
                reservation_id=reservation_id,
            ),
        )
        return ShadowCall(
            text=response.text,
            provider=response.provider,
            model=response.model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            cost_usd=response.cost_usd,
            latency_ms=(time.monotonic() - started) * 1000,
            response_hash=response.response_hash,
        )

    def settle(self, reservation_id: str) -> dict:
        return self.budget.settle_batch(
            reservation_id,
            command_id=f"{self.shadow.charged_to}:settle",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("verify")
    run = subparsers.add_parser("run")
    run.add_argument("--execute-paid", action="store_true")
    run.add_argument("--audit-report", type=Path, required=True)
    run.add_argument("--candidate-commit", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    shadow = PublicationShadow.open(ROOT)
    if args.command == "verify":
        print(shadow.verify())
        blockers = shadow.execution_blockers()
        print({"execution_blockers": list(blockers)})
        return 0
    if not args.execute_paid:
        raise PublicationShadowError("paid run requires --execute-paid")
    audit = verify_audit_gate(args.audit_report, args.candidate_commit)
    output = ROOT / "works/w0009/publication_shadow/results"
    adapter = BudgetRouterAdapter(shadow, output)
    result = shadow.run(
        adapter,
        output_dir=output,
        secrets=adapter.config.secrets.values(),
        execution_evidence=audit,
    )
    print(result)
    return 0 if result["status"] == "COMPLETE_AWAITING_BLIND_ANALYSIS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
