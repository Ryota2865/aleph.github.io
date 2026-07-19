# Formal milestone audit — ALEPH Phase 4 (w0009 L2 era intervention)

## Candidate identity (frozen)
- `git write-tree` = **780a70ec6b80e92cb5f6ab3dab78ab7e49744244** (matches the immutable candidate), base HEAD = `d7942dc`, branch `main`.
- No candidate change unstaged; `git diff` (tracked) empty; `git diff --cached --check` clean.
- Staged delta = w0009 evidence + 6 source files + docs/tests/plan. Only auditor pytest scratch (`.pytest_tmp/`) is untracked; it is outside the candidate index and does not alter the tree hash.

## Independent verification results
- **Reproduced tests** (`.venv`, `ALEPH_LOCAL=0`, local `TMPDIR`): full non-local suite **320 passed, 1 deselected**; focused `test_w0009_runner.py` **23 passed**. `bash scripts/doctor.sh` → **failures=0** (2 benign warnings). Construction evidence independently confirmed, not trusted.
- **Independent fault injections (my own, not Codex's):** envelope must sum to cap / reject empty/negative/bool; author substitution → `ManifestError` *before* any adapter call (fable-5 path proceeds to adapter); era leakage into `era_unpinned` rejected; envelope drift rejected; insufficient all-phase envelope fails closed before adapter; jury-before-select, promote-before-select, double blind-selection, promote-before-jury, promote-wrong-arm, double-promotion all rejected; tampered event → hash-chain break rejected; scope over-cap → `BudgetExceeded` before charge. All passed.

### Charter items — each independently confirmed
1. **Phase 3 interfaces reused, no broad DSL** — runner drives `ExperimentRun`/`EvaluationPacket`/`TransitionCommit`/`pipeline_to_draft`/`run_work`; era markers, decision rules, era-level logic are local constants/functions in `scripts/run_w0009.py`. Not promoted to a generic framework. Added core code is minimal general seams only.
2. **w0008 & existing works untouched** — only `works/w0009/*` added; zero w0008 or other tracked artifacts modified.
3. **Author fixed to `claude-fable-5`, substitution fails before adapters** — config `author_primary`=`anthropic/claude-fable-5`; `stage_prepare` rejects mismatch (`run_w0009.py:322-327`) before `choose_intent`; FI-verified; blind selection `decided_by=claude-fable-5` (event 7).
4. **Pre-registration frozen before paid execution** — manifest immutable (`experiment.py:111`), `_validate_manifest` freezes kernel/variants/arms/order/envelope/fixed conditions; envelope sums to 12.0; all-phase envelope + author + atlas checked before the first adapter call.
5. **Blind → jury → single canonical promotion** — events #7 blind_selection → #9 jury_reveal → #10 canonical_promotion (once); guards FI-verified.
6. **Call/charge provenance separates API vs local** — API calls → `experiment:exp-w0009-l2-era-pin`; local scout/jury → `work:{arm}:local` (`pipeline.py _experiment_charge_target`).
7. **All-phase cap fails closed before provider charge** — `Budget.precheck` scope branch raises `BudgetExceeded`; `scope_remaining` uses *identical* spent computation to `precheck`, so the L7 stop decision sees exactly the enforced gate; real rejection recorded (event 13: remaining $0.754550 < reserved $1.006250, rejected before provider execution).
8. **Preserved prepare L1** — first intent call durably logged as `L1`; relabelled to `prepare` for phase accounting (`_phase_costs`) and disclosed via deviation #1.
9. **Packet/effective constraints consistent L4–L7** — both arms share `effective_constraints_hash 2a42c728…`; packet hashes recorded and re-validated (`_validated_packet`).
10. **Incomplete jury parse & partial canonical review disclosed, no regeneration** — `INCOMPLETE_PARSE` with empty scores (jury_reveal.json); deviations #8 (jury) and #12 (cycle-5 interrupt); call/charge/response hashes preserved.
11. **Canonical stops at SHELVE via budget; no publish; no reflection/Phase 5; legacy L8 label distinguished** — checkpoint `state=SHELVE, stop_path=budget`; decisions show `L7 publication:SHELVE` + `resource_stop`, zero PUBLISH; `L8 題を確定: 第一信` legacy title label present, but no poetics reflection executed (`CanonicalL6L7Deps` omits the hook) and no Phase 5; deviation #14 discloses the label distinction.
12. **Three-face consistency** — `RULE_4_LEVEL_SPLIT_OR_MIXED` and **$11.245450 / $12.00** identical across `works/w0009/experiment/report.md` (total_spent 11.24545), `reports/EXP_w0009_l2_era_20260719.md`, and `docs/research/EXP_w0009_l2_era_20260719.html`. Decision-rule recomputation (control=mixed, intervention=low) reproduces RULE_4.
13. **Absent provider statements → unreconciled** — report `reconciliation_status: unreconciled`; `matched` not claimed.
14. **Monthly cap owner-approved $71** — `config/budgets.yaml`, `test_design_invariants`, PLAN all = 71.0.
15. **No acceptance weakening** — tests only added; the one changed assertion tracks the owner’s $71 decision; the `budget_exhausted → SHELVE` gate is strictly more conservative (never publishes).
16. **Event integrity** — 14-event hash chain intact; 9 deviations, matching the reports.

## Findings

No P0 / P1 / P2 findings.

Residual P3 observations (disclosed in-artifact; non-blocking, consistent with the runbook’s allowance):
- **P3 — phase allocation overrun.** `canonical_L6_L7` spent **$5.012720** vs $3.50 allocation (~43% over); disclosed via deviations #11/#12/#13 and the cost table. Per preregistration, phase allocations are report boundaries and the aggregate $12.00 is the sole enforced gate (which held). `scripts/run_w0009.py:833` / `reports/EXP_w0009_l2_era_20260719.md:78`.
- **P3 — raw prepare provenance label.** The first paid intent call remains labelled `phase=L1` in raw `calls.jsonl`; only reporting normalizes it to `prepare` (`scripts/run_w0009.py:823-829`). Disclosed via deviation #1.
- **P3 — jury comparison unavailable.** `INCOMPLETE_PARSE` leaves blind-choice/jury-argmax agreement unknown (not `false`); secondary observation lost by design, no regeneration.

## Uncertainties / uninspected areas
- The paid LLM run was **not** re-executed; I verified durable artifacts, deterministic logic, and public-interface fault injections only.
- Provider-side billing statements are absent by design; external reconciliation is unverifiable here and correctly remains `unreconciled`.
- The blind-label shuffle internals (seed 9009 → A/B mapping) were not recomputed; I relied on the recorded event and design.
- Per-unit classifier annotation correctness (single-annotator) and literary quality of drafts are out of audit scope; I verified aggregates against the reports and re-derived the primary rule.

VERDICT: PASS
