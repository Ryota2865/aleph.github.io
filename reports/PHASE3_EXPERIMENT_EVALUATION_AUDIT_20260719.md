## Formal Phase 3 milestone audit — ALEPH "Experimentと評価文脈を一級化する"

**Auditor:** independent Claude Code session (not the construction agent).
**Method:** read-only inspection + independent reproduction. No repository file was edited, staged, or created; all fixtures ran from `/tmp` and the scratchpad.

### Candidate identity (observed)
- Branch `main`; `git write-tree` = `354749a9d924fe7ecdd3e7a4bae3d946d28d1d78` — **matches** the audited tree in the prompt.
- All 19 candidate files are staged (`git diff --cached --name-status`) with a clean working-tree column; re-checked after all test runs — `write-tree` unchanged, **no post-staging drift** in any candidate file.
- `git diff --cached --check` — clean (no whitespace/conflict markers).
- Working-tree-only, non-candidate edits present at session start (`scripts/aleph_cycle.sh`, `doctor.sh`, `start_local_stack.sh`) are **not** in the staged tree and are correctly excluded from the candidate.

### Verification reproduced independently
- Focused Phase 3 suite (`tests/test_phase3_experiment_evaluation.py`, `-m m6`): **9 passed**.
- All non-local tests (`-o addopts="" -m "not local"`): **293 passed, 1 deselected** (the `local` GPU test).
- Repository snapshot audit (`scripts/audit_repository_snapshot.py`): **exit 0**; inventories existing works/ledgers/experiments/formal-audits without error.
- Snapshot/README consistency (`tests/test_repository_snapshot.py`): **5 passed**.
- Own adversarial fixtures (`/tmp/adv.py`, 33 assertions across all 7 required injection categories): **33 passed, 0 failed** — event tamper/reorder, blind leakage, reveal-before-select, second-selection, promote-before-reveal, wrong-arm promote, promote idempotency/conflict, expired vs active revoke, malformed amendments (bad action/target/missing text/bad scope), packet field/hash/effective-hash tampering, reconcile amount/scope/duplicate/missing-provenance mismatches, and cap-persist-across-restart + over-cap reject.

### Coverage findings (observed evidence)

1. **ExperimentRun** (`aleph/core/experiment.py`): normalized immutable `manifest.json` (`open` rejects mutation, L90–91); append-only hash-chained events with per-row `previous_hash`+`event_hash` verification (`events`, L104–120) — corruption and reordering both raise. Arm/work identity bijection enforced (L146–158). Deviations require reason+preregistration (L160–174). One canonical promotion, selected-arm-only, reveal-ordered, idempotent, conflict-rejected (L255–283). Legacy w0008 JSON kept as projections carrying `source_event_id/hash`; events are authority on reuse (`run_w0008.py` L897–961, L1002–1035, L1288–1320).

2. **Call/charge provenance** (`aleph/core/llm.py`, `budget.py`): `CallContext` + fail-closed check raises `ProvenanceError` **before** provider invocation when `experiment_id` present but any of command_id/work_id/phase/arm/charged_to missing (L232–271); provider-after-call charge failure preserves the call as `billing_status: unreconciled`, `charge_id: None` rather than fabricating a charge (L349–360). `Budget.charge` appends an immutable charge event (unique `charge_id`), returns it, and persists `charge_events` as the authority with the aggregate as projection; restart replays events (`_restore`, L221–234). Reconcile detects duplicates, missing provenance, and amount/scope mismatch (`reconcile`, L285–415).

3. **Budget envelope**: experiment sub-cap registered as an immutable scope limit (`register_scope_limit`) enforced in `precheck` on the summed `charge_events` for the scope — cumulative across periods and restarts (verified). Both the pre-call estimate (conservative UTF-8-byte upper bound, L211–214) and the post-call actual charge are checked against the cap, so select and canonical-L6 are inside the envelope. `_charge_amount(api)==resp.cost_usd==logged cost_usd`, so production reconciliation can legitimately reach `matched`. The 588 legacy rows lacking provenance reconcile as `unreconciled`, never matched.

4. **Blind selection**: selector receives only shuffled letter labels, candidate text, and technical-floor data; arm names, label mapping, and jury data are unreachable until the selection event is appended (`select_blind`, L176–232). Reveal-before-selection and second selection fail closed.

5. **Canonical promotion / consumers**: `WorkReader._canonical` consumes the promotion **event** as authority when `experiment/events.jsonl` exists, falling back to legacy `meta.json` otherwise (`work_snapshot.py` L402–426).

6. **Constraints/EvaluationPacket** (`constraints.py`, `evaluation.py`): source/scope/priority/expiry modeled; add/replace/revoke only; expired/out-of-scope amendments do not apply; malformed/ambiguous fail closed; revoked constraints excluded from `effective_constraints` but retained and explicitly marked non-penalizable in `render_for` ("減点してはならない"). One canonical packet hash + separate effective-constraints hash; `validate()` fails closed on either disagreement.

7. **L4–L7 wiring** (`pipeline.py`, `review.py`, `revise.py`, `write.py`, `stopping.py`, `publication_gate.py`): all four layers receive the packet; `run_review`/`decide_stop`/`decide_publication` call `packet.validate()` before doing work and record `evaluation_packet_hash`+`effective_constraints_hash` in review markdown and trajectory rows. Hash disagreement raises before any reviewer adapter runs (test confirms `calls == 0`).

8. **Compatibility / non-goals**: staged diff touches only code/tests/designs — **no `works/` or `state/` file is modified**; existing experiment seeds parse through the new resolver (snapshot audit exit 0). No generic DSL/workflow engine; no PLAN terminal-state, budget-cap-value, Phase 4, or w0009 change.

### Residual observations (P3 — non-blocking)

- **P3 — legacy prose vs structured revocation.** `aleph/pipeline.py:874-889` still feeds the legacy `experiment.criteria_constraints` string into `derive_criteria`→`criteria.md`, which the packet then carries verbatim as `packet.criteria`. Revoking that legacy constraint via a structured amendment targeting `legacy.criteria_constraints` removes it from `effective_constraints` (and marks it non-penalizable) but not from the baked `criteria.md` prose. This matches the design's explicit "does not infer revocation from prose"; structured constraints are the supported, tested revocation path. Residual risk only.
- **P3 — stricter global-cap enforcement side effect.** `Budget.charge` now re-`precheck`s the actual amount (`aleph/core/budget.py:150-163`), so a call landing over the **global** api cap now raises post-provider (logged `unreconciled`) where it previously recorded silently. The cap value and policy are unchanged and this is more fail-closed, but a run near $65 could see a call throw. Worth noting, not a defect.
- **P3 — `WorkReader._canonical` returns `canonical=True` for the experiment's main (non-arm) work whenever a promotion exists (`work_snapshot.py:417-418`, `arm_name is None`). Loose but not consumed as authoritative arm identity. Minor.
- **P3 — `criteria_text` in `pipeline_to_draft` (`aleph/draft/write.py:170`) is read but then superseded by the packet's L4 render for proposals/evolve — a likely dead read. Cosmetic.

No P0/P1/P2 findings. Every Phase 3 acceptance criterion and design invariant reproduced as specified, and each required failure-injection path fails closed.

VERDICT: PASS
