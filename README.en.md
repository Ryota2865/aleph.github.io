# ALEPH

[日本語版](README.md)

An autonomous production system for literary expression with LLMs. It searches for vacant niches in the literary ecosystem and creates works that inhabit them.

- **Design blueprint (canonical)**: [PLAN.md](PLAN.md) — the complete architecture, decision policies, and milestones
- **Change history**: [PLAN_CHANGELOG.md](PLAN_CHANGELOG.md)
- **Licenses**: [LICENSES.md](LICENSES.md) — code = MIT / works and production records = CC0 / documents = CC-BY 4.0

## Status

All M0–M6 milestones (the closed loop of exploration, materials, composition, drafting, critique, shelving, and publication) have been implemented and accepted. The designer (Claude Fable 5) writes the contracts (acceptance tests), while implementation is carried out under cross-audit by construction agents (Claude Code / Codex / pi / hermes) (PLAN §10 and §12).

- **Integrated runs**: w0001–w0004 completed with real LLMs. w0001–w0003 were automatically SHELVED with the audience set to “self”. w0004 was the first work to reach the final publication-gate stage after passing the quality floor in an experiment forcing an LLM audience (held pending the human approval `first_publish_ack` for the initial publication).
- **M7 sprint (2026-07)**: Work-specific material generation, measured niche scoring, repair of the revision cutoff, and the initial wiring of §5.4’s AI-specific techniques (anti-cliché and token-layer poetics). See [PLAN_CHANGELOG.md](PLAN_CHANGELOG.md) 0.7.14 for details.
- **Public site**: `docs/` (GitHub Pages). It displays an honest empty state when no works have been published. Serve it through Settings → Pages → `main` / `/docs`.

## For implementers

```bash
uv sync --extra dev
uv run pytest -m 'not local'   # design invariants + all milestone acceptance tests (must always stay green)
uv run pytest -m m0            # acceptance criteria for an individual milestone (specify m0..m6)

# Exploration → atlas → niche (requires llama-server / bge-m3; scripts/start_local_stack.sh)
uv run python -m aleph.cli explore
# Create a work and run the closed loop
uv run python -m aleph.cli new --hint "..."
uv run python -m aleph.cli run --work w0001
uv run python -m aleph.cli status   # balances for the three budget pools
```

- Design invariants are fixed in `tests/test_design_invariants.py`. A change that turns them red is a design change and requires a record in PLAN_CHANGELOG plus review by the designer.
- Changes that weaken acceptance tests (removing assertions or adding skips) fail the audit (PLAN §12).
- Secrets belong only in `.env`. Tests detect plaintext secrets in code, configuration, and logs.

## Publication (two layers, PLAN §8)

- Surface layer: the reader-facing site (final works + production notes)
- Deep layer: the complete production record in `works/` (defective drafts, critiques, decision logs, and the SHELVE graveyard) — a machine-readable archive

Signatures list participating models with their roles. ALEPH does not pretend there is a single “author”.
