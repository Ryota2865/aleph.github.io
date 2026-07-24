# Formal milestone audit runbook

This runbook operationalizes `PLAN.md` §12. It does not change the audit roles, acceptance
criteria, or design authority defined there.

## 1. Freeze the candidate

Complete implementation and independent construction-agent verification before formal audit.
Record:

- branch and `git status --short`;
- the relevant acceptance and full non-local test results;
- `git diff --check`;
- one immutable candidate identity: a commit SHA, or `git write-tree` after every candidate file
  has been staged and no candidate change remains unstaged or untracked.

Do not describe a dirty HEAD alone as the audit target. If a staged tree is used, include its tree
hash in the audit prompt and report.

## 2. Commission the independent auditor

Use the cross-auditor required by `PLAN.md` §12. The auditor must inspect read-only, reproduce the
acceptance checks independently, classify findings P0–P3 with file/line evidence, and end with
exactly `VERDICT: PASS` or `VERDICT: FAIL`.

For a Codex-built milestone, prepare a paste-ready Claude Code prompt. If direct transfer is denied
because it would disclose workspace contents or automate an external consumer service, do not
circumvent the denial. Ask the owner to run the prompt in the Claude Code app and return the complete
response. The formal auditor must not edit the candidate or write its own report into the repository.

Treat tests-green, a Hermes pre-audit, and the formal verdict as separate evidence. Hermes never
replaces the Claude Code milestone audit required for Codex-built work.

The report's final non-empty line must be exactly `VERDICT: PASS` or `VERDICT: FAIL`. Prose,
quoted verdicts, bold Japanese labels, filenames, and directory order are not machine verdicts.

## 3. Preserve FAIL and repair

Copy the auditor response from its report heading through the final verdict without changing its
meaning. Store it under `reports/` with `AUDIT` in the filename so `RepositorySnapshot` can inventory
it. Do not delete, overwrite, or rewrite a FAIL artifact after repair.

Register every new formal artifact in `config/formal-audits.json` in the same closure change. Use
the next unique monotonic `sequence`, the factual `recorded_on`, the audited implementation's
`target_changelog`, its immutable `candidate_tree`, a proof `candidate_commit` with that exact tree,
and a durable `candidate_ref` under `refs/tags/audit-candidate/`. A focused re-audit also records
`supersedes`. The PASS entry declares only the mechanical `closure_paths` allowed after the audited
tree. Pre-ledger artifacts remain in `legacy_unordered`; they are retained evidence but cannot
determine the latest verdict. An unregistered artifact, invalid ledger entry, missing object/ref,
or tree mismatch makes the latest-verdict projection `UNKNOWN`, never an inferred PASS.

For every blocking finding:

1. reproduce the observable failure with a focused RED test;
2. make the smallest authorized correction;
3. run focused and full non-local verification;
4. ask the same auditor for a read-only re-audit of the failed scope.

Save the re-audit as a separate artifact. A PASS may retain explicit P3 observations; record them as
residual risks without silently expanding the milestone.

## 4. Close after PASS

After `VERDICT: PASS`, make only closure changes:

1. add the raw PASS audit artifact while retaining earlier FAIL artifacts;
2. create a proof commit with the audited candidate tree, retain it under an
   `audit-candidate/<scope>-<date>` tag, and register the PASS artifact, tree, commit, full tag ref,
   and closure paths in `config/formal-audits.json`; keep the audited repair's `target_changelog`
   number unchanged;
3. refresh the `RepositorySnapshot`-derived README markers in both languages;
4. update the execution plan status, the existing target entry in `PLAN_CHANGELOG.md`, and
   `PROGRESS.md` without creating a new design version or changing canon;
5. run the README snapshot consistency test, all non-local tests, and `git diff --check`;
6. confirm that the final diff beyond the audited candidate contains only audit evidence and
   mechanical closure documentation.

Push the audit-candidate tag with the eventual branch so the proof commit remains reachable after
clone. `RepositorySnapshot` may report `CURRENT` from a clean HEAD or a fully staged index only when
the candidate-to-current diff is wholly inside the declared closure paths.

Any post-audit change to code, tests, contracts, acceptance criteria, or non-derived design meaning
invalidates the PASS for that candidate and requires another audit. Audit evidence and mechanical
closure documentation do not require re-audit when their consistency checks pass.

Commit or push only after owner authorization. Report the candidate identity, final commit, formal
verdict, verification results, residual risks, and whether the worktree is clean.
