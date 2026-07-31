# W0009 Publication-Input Shadow Runner — Independent Read-Only Audit

- Audit date: 2026-07-31 (report slug: 20260730, matching the sanctioned artifact path)
- Auditor: Claude Code (Opus 4.8), independent read-only pass
- Method: read-only inspection + independent re-execution; all fault injection confined to `/tmp`; repository not modified during the audit

## Candidate identity (bound for the paid-run gate)

- Branch: `codex/phase6-r9-audit-ledger-path-disjoint`
- Candidate commit: `d4bc98b3220bda82fabe3c558de2e1111b899542`
- Candidate tree: `ac280ff1ad9d3cc1deaaec148d7f62c10e37d2dd`
- Preregistration commit: `8a5bd487252fdc328abc535bc26b7af6f571148d` (`8a5bd48`)
- Preregistration manifest: `works/w0009/publication_shadow/preregistration.json`
- Preregistration manifest SHA-256: `c327aaf811e05433b1db76bf4ba3955a54e30470857bf12697d29053b07b2f32`
- Target changelog: 0.7.20-40

## Reading discipline

Tests-green and the formal verdict are kept separate. Passing tests are one
input among several; they do not substitute for the point-by-point structural
verification below. Each item separates **Observed evidence** (what a tool
directly showed), **Inference** (what I conclude from it), and **Uncertainty**
(what remains unproven, chiefly the un-run paid provider path).

---

## 0. Identity invariance (audit point 1)

**Observed evidence.** At audit start and at audit end `git rev-parse` reported
branch `codex/phase6-r9-audit-ledger-path-disjoint`, HEAD
`d4bc98b…`, tree `ac280ff…`, and `git status --porcelain=v1` was empty
(no staged/unstaged/untracked entries). `git diff --check` returned clean.
The candidate commit and tree resolve exactly to the values above.

**Inference.** The read-only audit (verify command, pytest, `/tmp` harness) did
not mutate the candidate. Candidate identity is invariant across the audit.

**Uncertainty.** None. (This report file, written after the audit proper, is the
sole post-audit filesystem addition; it is the sanctioned closure artifact
enumerated in the runner's `POST_AUDIT_ALLOWED_PATHS`.)

## 1. Preregistration lineage and pre-observation freezing (audit point 2)

**Observed evidence.** `git merge-base --is-ancestor 8a5bd48 d4bc98b` → exit 0
(candidate descends from prereg). `git log 8a5bd48..d4bc98b` shows exactly two
descendant commits: `5c80708` (build runner) and `d4bc98b` (harden gate); the
runner did not exist at `8a5bd48`. The manifest blob SHA-256 at `8a5bd48` and at
HEAD are byte-identical (`c327aaf8…`), i.e. the manifest was frozen before the
runner was written and never rewritten. The manifest freezes body identities
(full/excerpt/omitted char counts, byte counts, SHA-256), shelf summaries, both
intent prompts (SHA-256), the schema text (SHA-256), model/provider/pricing
identity (`config/models.yaml@sha256:…`), and the selection rules — all prior to
any result observation (`status: preregistered_not_run`).

**Inference.** All decision-affecting inputs were fixed before results could be
seen; the runner cannot retroactively influence what was preregistered.

**Uncertainty.** None material.

## 2. Read-only reconstruction with no paid call (audit point 3)

**Observed evidence.** `uv run python scripts/run_w0009_publication_shadow.py verify`
printed:
`{'experiment_id': 'exp-w0009-publication-input-shadow-v1', 'manifest_sha256':
'c327aaf8…', 'packet_count': 2, 'reserve_usd': 3.9968, 'status':
'VERIFIED_NOT_RUN'}` and blockers
`['earliest run date has not arrived', 'monthly API cap is not the preregistered
45 USD', 'publish.max_per_month is not the preregistered value 4']`.

**Inference.** Verify reconstructs every frozen identity from repository state
with no provider call. status=VERIFIED_NOT_RUN, packet_count=2,
reserve_usd=3.9968, and all three preregistered blockers match the expected
values. The `verify` code path performs only reads.

**Uncertainty.** None.

## 3. Body reconstruction and body-only variation (audit point 4)

**Observed evidence.** Independent recomputation from `works/w0009/drafts/v2.md`:
full = 11,139 chars; excerpt = `text[:4000] + "\n……\n" + text[-2000:]` = 6,004
chars; omitted middle = 5,139 chars. `_intent_prompt` with the body masked is
byte-identical across two distinct bodies. Design doc §3 line 91 states only the
bytes after `作品（抜粋）:` may differ between arms.

**Inference.** The two intent prompts differ solely in the work body; frame,
audience line, and instructions are constant. Char counts match the manifest.

**Uncertainty.** None.

## 4. Strict parse only; no prose fallback; parse-failure ≠ SHELVE (audit point 5)

**Observed evidence.** Runner line 409 calls
`parse_model_output(intent.text, schema=_INTENT_SCHEMA, fail_closed=True)` and
nothing else. `parse_model_output` signature is
`(text, *, schema, fail_closed=True)`; with `fail_closed=True` any scan warning,
absent JSON, or multiple JSON values yields `value=None`. The decision mapping
(lines 512–518) is: `publish is True` → PUBLISH, other parsed value → SHELVE,
`value is None` → **PARSE_INCOMPLETE**. `test_shadow_does_not_use_production_prose_fallback`
feeds prose (`"この作品は公開するに値する。"`) and observes classification
`NO_JSON` and decision `PARSE_INCOMPLETE`.

**Inference.** The shadow never consults the production publish/withhold prose
fallback, and a parse failure is recorded as PARSE_INCOMPLETE — it is not silently
read as SHELVE.

**Uncertainty.** None.

## 5. Call ordering and statelessness (audit point 6)

**Observed evidence.** `run()` completes both intent calls in one loop
(lines 394–416), then a second loop (417–445) issues a shelf-comparison call only
for arms whose decision is PUBLISH. Each prompt is a fixed string
(`self._prompts[packet_id]`, `self._comparison`); no prior response, arm name, or
comparison purpose is interpolated into any later prompt. `arm`/`phase` appear
only in `CallContext` provenance metadata, never in the message body.
`test_both_primary_intents_finish_before_conditional_comparisons` observes phase
order `[intent, intent, shelf_comparison, shelf_comparison]`.

**Inference.** The two intents complete first; PUBLISH arms then run an
independent, stateless shelf comparison. Calls carry no cross-call state in the
prompt.

**Uncertainty.** None.

## 6. Retry contract: 0/0/1 and preserved defaults (audit point 7)

**Observed evidence.** Manifest `attempt_policy` = semantic 0 / transport 0 /
attempts_per_slot 1. Adapter passes `transport_retries=0` and the BatchSpec sets
`semantic_retries=0`; `attempt.json` records `attempts_per_slot: 1`. Router
(`aleph/core/llm.py`): `transport_retries = overrides.pop("transport_retries", 2)`;
`if type(transport_retries) is not int or transport_retries < 0: raise ValueError`
(before budget precheck and before the provider call); retry loop is
`for attempt in range(transport_retries + 1)`. Note `type(x) is not int` rejects
`bool` (since `type(True) is bool`). Tests
`test_router_transport_retries_can_be_disabled` (calls==1),
`test_router_rejects_invalid_transport_retry_contract_before_provider`
(`[True, -1, 0.5, "0"]`, provider.calls==0), and
`test_router_default_transport_retry_count_is_preserved` (calls==3, logged
`transport_retries==2`) all pass.

**Inference.** transport_retries=0 ⇒ exactly one attempt; unspecified ⇒ 3
attempts (2 retries) as before; bool/negative/non-int are rejected before any
provider call.

**Uncertainty.** None.

## 7. Reserve derivation, ordering, cap, and work-identity split (audit point 8)

**Observed evidence.** `verify()` recomputes
`math.fsum(slot.max_usd) == total_max_usd` with abs_tol 1e-12; slot ceilings
1.0592 + 1.2192 + 0.8592 + 0.8592 = 3.9968 USD. In `run()`, `adapter.reserve()`
(line 373) precedes the first call loop. `execution_blockers` requires
`config.budgets["api"]["usd_per_month"] == 45.0`. The BatchSpec and CallContext
use `work_id = "w0009-publication-shadow"` (`SHADOW_WORK_ID`), distinct from
canonical `w0009`; `charged_to = experiment:exp-w0009-publication-input-shadow-v1`.
`test_budget_reservation_uses_separate_shadow_work_identity` charges `w0009`
independently and confirms the shadow reserve draws from the shared api cap
without touching the `w0009` balance.

**Inference.** The $3.9968 worst-case reserve is derived (not hand-entered),
taken before the first provider call, sits inside the $45 monthly api cap, and is
booked to a separate shadow work identity — canonical w0009 accounting is
untouched.

**Uncertainty.** The per-slot ceilings (input/output token bounds) were not
re-derived against a live tokenizer; they are enforced as ceilings, so actual
paid usage can only be ≤ reserve, but their tightness is unverified (paid path
un-run — by design).

## 8. Attempt marker and duplicate-run refusal (audit point 9)

**Observed evidence.** `run()` refuses when the results dir already exists
(lines 370–371) **before** `adapter.reserve()`. After reservation and before the
first provider call, it atomically writes `attempt.json` (lines 382–392).
`test_existing_result_path_blocks_duplicate_paid_attempt` confirms
`adapter.reserved is False` when the path pre-exists;
`test_manifest_drift_fails_before_adapter_reservation` confirms drift aborts
before reservation.

**Inference.** A crash after reservation leaves the results dir present, so any
re-invocation is refused rather than silently becoming an unrecorded retry;
`retry 0` cannot be bypassed by re-running.

**Uncertainty.** None.

## 9. Evidence capture and secret scrubbing (audit point 10)

**Observed evidence.** Each observation records: raw response SHA-256 and the
scrubbed raw text file under `results/responses/`; parser ok/classification,
fragment, source_span, warnings; decision (PUBLISH / SHELVE / PARSE_INCOMPLETE);
shelf comparison (`RECORDED_UNSCORED` or `NOT_TRIGGERED`); prompt/completion
tokens; declared cost; latency; settlement and `execution_evidence` (audit
identity) at the top level of `observations.json`. `_call_and_record` runs
`scrub_secrets(call.text, secrets)` before hashing/writing; the CallLogger is
constructed with `secrets=config.secrets.values()`.

**Inference.** All preregistered `record` fields are captured and pass through
secret scrubbing before persistence.

**Uncertainty.** Actual provider token/cost/latency values are only observable on
a live run (un-run by design); capture *structure* is verified, live *values* are
not.

## 10. Blind annotation packet does not leak the mapping (audit point 11)

**Observed evidence.** `_blind_annotation_packet` emits `mapping_disclosed: False`,
items with only `packet_id / parse_status / decision / reason` and
`middle_reference / decision_relevant = "PENDING"` (no `body`, no excerpt↔full
mapping, no source/response quotes). Instruction text warns not to inspect
`preregistration.json` before both annotations are fixed. The packet_id→body
mapping lives only in the manifest. `test_shadow_calls_…` asserts
`mapping_disclosed is False` and `all("body" not in item …)`.

**Inference.** The runner does not pre-judge the middle reference and does not
disclose which packet is excerpt vs full before both raw responses are fixed.

**Uncertainty.** None.

## 11. Canonical immutability, before and after (audit point 12)

**Observed evidence.** `_verify_baseline_files()` hash-checks
`works/w0009/checkpoint.json`, `decisions.jsonl`, `calls.jsonl` against the
manifest baseline; it runs during `verify()` (pre-run) and again after the call
loop (lines 462–468). On mismatch the status becomes
`INCOMPLETE_IMMUTABILITY_VIOLATION` (never a COMPLETE state). The runner's only
write targets are under the `results/` output dir (responses, attempt.json,
observations.json, blind packet) and the adapter's `results/calls.jsonl` — it has
no write path to `drafts/`, `final/`, the public site, `poetics/`, or house-style
annotation results (it only *reads* `drafts/v2.md`). `test_shadow_calls_…`
asserts `works/w0009/final` is never created.

**Inference.** The three canonical files are hash-compared on both sides of the
run and a change forecloses a COMPLETE verdict; no code path mutates the other
protected artifacts.

**Uncertainty.** None.

## 12. Paid-CLI audit gate (audit point 13)

**Observed evidence.** `verify_audit_gate` enforces: last non-empty report line
strictly `VERDICT: PASS`; candidate commit and tree substrings both present in
the report; clean `git status --porcelain`; current HEAD is candidate-or-descendant
(`merge-base --is-ancestor commit head`); and post-candidate diff
(`diff --name-only commit..head`) is a subset of `POST_AUDIT_ALLOWED_PATHS`.
That allowlist = {PLAN_CHANGELOG.md, PROGRESS.md, README.en.md, README.md,
config/budgets.yaml, config/formal-audits.json,
designs/next-designer-execution-plan.md, this report}. Tests
`test_audit_gate_binds_clean_head_commit_tree_and_terminal_pass` and
`test_audit_gate_rejects_post_audit_code_change` (rejects `aleph/core/llm.py`)
pass.

**Inference.** The gate rejects any post-candidate change to code, tests, the
runner, the manifest, or works. The allowlist contains only documentation /
audit-ledger / budget-deadline files plus the audit report itself — consistent
with "formal closure docs, the fixed audit artifact, and the 2026-08-01
`config/budgets.yaml` deadline action."

**Uncertainty.** The commit/tree binding is a substring-presence check rather than
a structured field match; combined with the HEAD-descendant + clean-worktree +
allowlist conditions this is sound, but a report could in principle mention the
hashes in prose without a dedicated field. Non-blocking (see P3-1).

## 13. Shelf-comparison limitation is declared, not hidden (audit point 14)

**Observed evidence.** `_comparison_prompt` contains audience + shelf titles and
**no work body** (independently reproduced: `"…棚の既公開作:\ns1\ns2"`). The
manifest states `shelf_comparison.limitation: "the current stateless comparison
prompt contains shelf titles but no work body"` and `selection_endpoint: false`.
Design doc §4.2 lines 126–129: the output is *not* used as packet-selection
grounds and is routed to direct blocker review before canonical re-evaluation,
explicitly *not* silently patched during the shadow. In `run()` the comparison is
stored as `RECORDED_UNSCORED`; final `selection` is
`PENDING_BLIND_MIDDLE_ANNOTATION`.

**Inference.** The stateless comparison prompt's lack of work body is disclosed,
not concealed; the comparison is not used to select the input-length packet and
is explicitly deferred to direct blocker review.

**Uncertainty.** None.

---

## Independent re-execution (objective signals)

| Command | Expected | Observed |
| --- | --- | --- |
| `uv run pytest tests/test_w0009_publication_shadow.py -q` | 16 passed | **16 passed** |
| `uv run pytest -m 'not local' -q` | 453 passed, 1 deselected | **453 passed, 1 deselected** |
| `uv run python -m compileall -q aleph scripts` | clean | exit 0 |
| `git diff --check` | clean | exit 0 |
| `run_w0009_publication_shadow.py verify` | VERIFIED_NOT_RUN / 2 / 3.9968 / 3 blockers | matched |
| formal-audit projection | PASS / NEEDS_AUDIT / 0.7.20-40 | matched |

## RED reproduction on base `8a5bd48` (fault injection in `/tmp` only)

Base and candidate trees were exported with `git archive` into `/tmp`; a harness
drove each tree's real `Router`:

| Tree | `transport_retries=0` | unspecified caller |
| --- | --- | --- |
| base `8a5bd48` | provider.calls = **3** (RED — retry 0 not expressible) | 3 |
| candidate `d4bc98b` | provider.calls = **1** (GREEN — retry 0 honored) | 3 |

Base `aleph/core/llm.py` hard-codes `for attempt in range(3)` with no
`transport_retries` parameter, so the preregistered `attempts_per_slot=1` could
not be represented; the candidate parametrizes it to a single attempt while
unspecified callers retain 3 attempts.

## Findings by severity

- **P0 (blocking): none.**
- **P1 (serious): none.**
- **P2 (moderate): none.**
- **P3 (minor / advisory):**
  - **P3-1.** The audit gate binds the candidate commit/tree by substring
    presence in the report text rather than a structured field. Sound in
    combination with the other gate conditions; a future hardening could match a
    dedicated `Candidate commit:` / `Candidate tree:` field. (Observed: gate code
    lines 62–63.)
  - **P3-2.** `POST_AUDIT_ALLOWED_PATHS` is a little broader than the narrowest
    reading of "closure docs + budget deadline + audit artifact" (it also admits
    README/PLAN_CHANGELOG/PROGRESS/next-designer-execution-plan/formal-audits.json).
    All are documentation or audit-ledger files; none permit code, test, runner,
    manifest, or works changes, so the safety property holds. (Observed: allowlist
    definition, runner lines 27–38.)

## Tests-green is not the verdict

The 16 targeted tests and 453-test suite pass, but this verdict rests on the
structural verification above — manifest freezing before result observation,
strict fail-closed parsing, stateless ordering, the reserve/immutability/gate
invariants, and the base-vs-candidate retry reproduction — not on the green bar
alone. The one path not exercised is the paid provider run (correctly blocked:
pre-2026-08-01 date, caps not yet flipped, and this audit as the final gate);
its live token/cost/latency values remain unverified by construction, which is
the intended posture for a pre-execution audit.

## Conclusion

All fourteen audit points reconstruct from repository state with no paid call;
candidate identity is invariant across the audit; the preregistration is frozen
at `8a5bd48` before the runner existed and the candidate descends from it; the
retry-0 contract is reproduced RED on base and GREEN on candidate; and no P0–P2
finding was identified.

Candidate commit `d4bc98b3220bda82fabe3c558de2e1111b899542`,
candidate tree `ac280ff1ad9d3cc1deaaec148d7f62c10e37d2dd`.

VERDICT: PASS
