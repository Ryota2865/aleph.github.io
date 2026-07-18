# ALEPH agent guidance

`PLAN.md` is the design canon. Follow explicit user decisions and implementation requests within their stated scope.

When the user asks for evaluation, advice, review, or interpretation:

- assess the matter independently rather than treating the framing in the request as the desired conclusion;
- distinguish observed evidence, inference, interpretation, and speculation;
- when it could change the decision, examine both the strongest supporting case and the strongest counterargument;
- allow "no change" or "no additional document" as outcomes when they best serve the project;
- do not oppose an idea merely to demonstrate independence, and do not suppress exploratory or artistic hypotheses for lacking immediate proof;
- treat discussion as discussion: it does not by itself modify `PLAN.md` or authorize implementation.

Ideas may be explored and recorded when useful, provided their status is clear. Do not silently delete or rewrite an artifact the user has seen or relied on; propose the change and obtain authorization.

These rules govern the quality of judgment, not the direction of the judgment.

## WSL execution environment

- Run repository commands inside WSL as `ryota_tanaka`; the canonical checkout is
  `/home/ryota_tanaka/llm_literature`. Do not mix Windows Git state with WSL Git state.
- Keep GitHub CLI state in WSL (`~/.config/gh`). Use `gh auth git-credential`; do not create
  `.git-credentials` or print tokens in diagnostics.
- Run `bash scripts/doctor.sh` before environment-sensitive work. Add `--network` only when
  GitHub API access is needed.
- A failed `gh auth status`, NVML check, or `.git` write inside a sandbox may be a permission
  failure rather than broken configuration. Re-run the same read-only check with the required
  network/GPU permission before diagnosing it.
- Before local model work, verify RTX 3090 availability and port 8081. Never stop, replace, or
  reuse a server that does not advertise the requested model alias.
- `PLAN.md` and repository config remain canonical for ALEPH decisions. Personal skills only
  encode reusable execution workflows; they must not override project policy.
