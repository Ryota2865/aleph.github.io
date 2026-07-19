# Phase 3 design gate — Experiment and evaluation context

Date: 2026-07-19
Status: implementation gate (adopted Phase 3 only)
Designer / implementer: Codex
Independent milestone auditor: a separate Claude Code session

## Canon and scope

This gate implements only Phase 3 of `designs/next-designer-execution-plan.md`.
`PLAN.md` semantics, budget limits, lifecycle terminal states, Phase 4, and w0009 are unchanged.
Historical works and ledgers remain byte-for-byte unchanged. Legacy artifacts are accepted only by a
read-only compatibility adapter and are reported as legacy or unreconciled; they are never repaired by
inventing provenance.

## Observed legacy seams

- `scripts/run_w0008.py` independently interprets the manifest, arm costs, blind labels, jury reveal,
  and canonical promotion. Its cap check covers arm generation but not later select and canonical-L6
  calls.
- `Router` writes a cost aggregate and a call row as separate operations. `state/budget.json` persists
  totals but not charge events, so a call cannot be reconciled to a particular charge.
- L4 reads `seed.json`, L5 receives a constraint string, L6 reads `criteria.md`, and L7 reads trajectory
  and budget independently. `WorkSnapshot.effective_constraints` recognizes only the legacy string and
  has no amendment, priority, scope, or expiry semantics.
- Existing 588 call rows have none of `call_id`, `command_id`, `experiment_id`, `charged_to`, or a charge
  reference. They remain valid historical evidence but cannot be represented as fully reconciled.

## Deep modules and interfaces

### `ExperimentRun`

The seam is `aleph.core.experiment.ExperimentRun`:

```python
run = ExperimentRun.open(work_dir)
run.manifest
run.register_arm(arm, work_id=...)
selection = run.select_blind(candidates, selector=..., decided_by=...)
run.reveal_jury(rows, decided_by=...)
run.promote(arm, work_id=..., command_id=...)
run.record_deviation(...)
report = run.reconcile(calls_path=..., charge_events=..., provider_charges=...)
```

The interface hides manifest validation, arm/work identity, append-only event IDs, blind mapping,
reveal ordering, canonical uniqueness, experiment-cap reservations, deviations, and scope-normalized
reconciliation. Technique-specific classifiers and workflow orchestration stay outside the module.

Authoritative new state is `experiment/events.jsonl`; `experiment/manifest.json` is an immutable
normalized copy of the seed manifest. Existing w0008 JSON files are legacy projections. New projections,
when retained for human readability, contain the source event ID/hash and are never read as authority.

### Call/charge provenance

`CallContext` is the context passed through `Router.call`/`call_jury`. Every new call row has:
`call_id`, `command_id`, `work_id`, `experiment_id`, `phase`, `arm`, `charged_to`, and `charge_id`.
Non-experiment calls receive explicit system defaults; experiment calls fail closed when required
context is absent.

`Budget.charge` appends an immutable charge event before updating its projection and returns its
`charge_id`. The aggregate in `state/budget.json` is a projection of retained charge events, not a second
authority. A provider statement is an external adapter: absent provider data is `unreconciled`, never
assumed equal.

### `EvaluationPacket`

The seam is `aleph.core.evaluation.EvaluationPacket`:

```python
packet = EvaluationPacket.for_draft(work_snapshot, draft_version)
packet.hash
packet.effective_constraints
packet.render_for("L4" | "L5" | "L6" | "L7")
```

The packet contains intent, criteria, base constraints, structured amendments (source, scope, priority,
expiry), poetics version, atlas identity, and draft/provenance references. Canonical JSON determines one
SHA-256 hash. L4-L7 callers receive this packet rather than reading seed/criteria/trajectory independently.
Reviews and trajectory rows record both packet hash and effective-constraints hash.

Amendments are applied in ascending priority and manifest order. `add`, `replace`, and `revoke` are the
only actions. Expired or out-of-scope amendments do not apply. A revoked constraint is retained in packet
history but excluded from `effective_constraints`; the L6 rendering explicitly forbids penalizing it.
Malformed, ambiguous, or stale structured amendments fail closed. The legacy
`experiment.criteria_constraints` string is adapted as one active base constraint without attempting to
infer revocation from prose.

## Invariants and failure model

1. An experiment call without complete provenance is rejected before provider invocation.
2. Every charged call references exactly one charge event; duplicate IDs or amount/scope mismatch is
   `unreconciled` and prevents a matched report.
3. The experiment envelope includes every phase, including selection and canonical L6. Reservation or
   post-call charge beyond the cap raises before the next provider call and records no false match.
4. The selector receives neutral labels, candidate text, and allowed technical-floor data only. Arm names,
   label mapping, and jury data are unavailable until the selection event is durably appended.
5. Jury reveal requires a preceding blind-selection event. Promotion requires one selected arm and emits
   one canonical promotion event; a different second promotion is rejected.
6. L4-L7 reject a packet whose recomputed hash disagrees with its recorded hash. Reviews record the hash
   used, not a later reconstruction.
7. Constraints are resolved once in the packet. A revoked/expired constraint cannot re-enter through a
   stale `criteria.md` reader.
8. Append/projection failure is visible. No recovery path fabricates a call, charge, reveal, promotion, or
   amendment event.

## Migration order

1. Add public-interface tests and minimal `ExperimentRun`/`EvaluationPacket` implementations.
2. Add call context and append-only charge events; preserve legacy Budget/Router callers through explicit
   non-experiment defaults.
3. Route w0008-equivalent blind selection, jury reveal, promotion, and cap checks through `ExperimentRun`.
4. Route production L4-L7 through `EvaluationPacket`; retain compatibility parameters only for tests and
   legacy entry points, with one internal conversion to a packet.
5. Remove replaced direct authoritative readers/writers. Keep only named read-only legacy adapters and
   derived projections.

## Observable tracer bullets and acceptance verification

Vertical RED→GREEN order:

1. A structured revoke amendment produces an L6 packet that excludes the old constraint and says not to
   penalize it.
2. An experiment Router call missing provenance fails before the fake provider is invoked; a complete call
   writes a linked charge event.
3. A blind selector cannot observe arm names or jury data, and reveal-before-selection fails.
4. Select and canonical-L6 charges push a fixture over the experiment cap and are rejected.
5. A review records packet/effective-constraint hashes; injected disagreement fails closed.
6. Scope reconciliation reports calls/ledger/provider as `matched` only for equal linked events and reports
   missing provenance or amount/scope mismatch as `unreconciled`.

Final verification: focused Phase 3 tests, all non-local tests, explicit failure-injection cases above,
repository audit commands, `git diff --check`, then a formal independent Claude Code audit. Phase 4 and
w0009 remain out of scope even after PASS.
