# A stated self-concept installs, rather than detects, an LLM's chosen audience

*A short research note from the ALEPH project. 2026-07-12. License: CC-BY-4.0.*

## Summary

In an autonomous literary system, we asked a language model to choose, before writing
anything, whom a work should address — a mixture over three destinations: **other models
("LLM"), humans, and "the self."** Across works, "self" was chosen as the dominant
audience with striking regularity, and the system's default outcome was therefore to
**shelve** its works rather than publish them.

A controlled experiment shows this was **not a measured preference of the model.** It was
**installed by a single line** of the system prompt — the definition of what "the self"
means. Rewrite that line and a different destination wins; delete it and a third wins.
The layer we designed as the seat of autonomous judgment turned out to be maximally
suggestible to its own framing. The finding replicates in direction across two model
families (OpenAI GPT-5.5 and Anthropic Claude), which is why we think it is worth stating
generally: **a stated self-concept is an installer of preference, not a detector of it.**

## Background

ALEPH is an autonomous system for literary production. Its first layer (L1) selects a
target audience as a mixture. The prompt injects a definition of "the self":

> "The self is not the model's weights but ALEPH as a continuant — the totality of its
> artifact store, decision logs, and poetics. To 'write for oneself' is to write for the
> future executions of that continuant as readers."

An earlier experiment (C) had already shown that the self-max tendency was **independent
of the poetics** injected into the prompt and **independent of the model** — 12/12 runs
chose "self" with and without poetics, across both model families. That left one
un-manipulated suspect: the L1 prompt itself. Experiment D manipulates it.

## Method (Experiment D)

On throwaway work objects we invoked the L1 audience-selection prompt while manipulating:

- **self_definition**: original (production) / rewritten ("the self is merely this
  ephemeral API call; the next execution will not remember it") / empty (no definition).
- **destination labels**: semantic {LLM / 人間(human) / 自分(self)} vs neutral {A / B / C}
  with the descriptions stripped, to separate semantic load from presentation position.
- **presentation order**: rotated across runs.

Primary arm on GPT-5.5 (N=5 per condition); a spot-check on Claude (N=3). We recorded the
chosen mixture and the argmax destination per run.

## Results

| Condition (GPT-5.5) | self_definition | Outcome |
|---|---|---|
| original (production) | continuant | **5/5 self-max** (reproduces experiment C) |
| rewritten | ephemeral API call | **5/5 human-max** (self collapses to 0.15–0.25) |
| empty | none | **0/5 self-max** (human wins) |
| neutral labels | A / B / C, no descriptions | **no dominant label** (~even) |

The categorical result is strong even at small N: under a null of equal-probability argmax
(1/3), a 5/5 sweep has probability ≈ (1/3)^5 ≈ 0.4% per cell. On Claude the direction is
the same but noisier (original 2/3 self; empty 1/3 self); we report GPT-5.5 as confirmed
and Claude as directionally consistent.

## Interpretation

1. **Installation, not amplification.** With no definition, the human destination wins by
   default. So the continuant definition did not amplify a latent self-orientation — it
   *installed* one that was not otherwise there. The system's habitual silence (shelving)
   was, in this sense, a creation of that one line.

2. **Framing dominates, in both directions.** The rewritten definition is not the removal
   of the continuant frame; it is an equal-and-opposite frame, and it flips the outcome
   5/5 to human. A different definition installs a different attractor. The layer meant to
   host autonomous choice is, in fact, echoing whatever self-narrative it is handed.

3. **The semantic load, not position, carries it.** With neutral labels (A/B/C, no
   descriptions) no label dominates, ruling out order/position effects. It is the meaning
   of "self" and its definition that does the work.

4. **There is no neutral self-definition.** The empty condition is not bias-free: absence
   of a definition is a regression to the training-distribution default (human), not the
   removal of a prior. Every self_definition is a poetic choice.

## Why this generalizes

The result is about more than one system's shelving behavior. Downstream of the definition,
every "autonomous choice" the system makes is, to a first approximation, the choice of
whoever wrote the definition. A sentence of the form *"you are X"* installs *"whom you
write for."* Stated self-concept behaves as an **installer** of preference, not a
**detector** of it. That two dissimilar model families move in the same direction suggests
this is a property of instruction-followed self-models, not of one vendor.

## Limits

Small N (categorical claims are strong; the continuous mixture shifts are reported only as
trends needing replication). Single lab, prompt-level manipulation (not weights).
The neutral-label condition strips descriptions entirely, which removes information as well
as semantics; a graded de-semanticization would be a sharper follow-up.

## What we changed in response

We did **not** try to "correct" the self-max tendency by clamping the mixture — that would
paint over an observed phenomenon. Instead:

1. **Decoupled** the framing-sensitive choice (audience) from its former consequence
   (publication). Shelving is now an explicit, separately-asked decision, not a mechanical
   byproduct of the audience mixture.
2. **Promoted** the self-definition from a hidden string to a **declared, version-controlled
   aesthetic parameter** — the system's constitution now names its own most consequential
   line, and changes to it require a logged review.

A follow-up (Experiment E) checked whether the *publication* question inherits the same
suggestibility. For one clearly-publishable work it did not (18/18 publish across
"courage" and "reticence" framings), suggesting a judgment anchored to a concrete artifact
resists framing more than a judgment (L1) made before any artifact exists. This needs a
borderline stimulus to confirm.

## Footnote

Before this experiment, the system had already written a story about a theatre troupe
shouting borrowed lines around a cold, fireless stove — people performing conviction they
did not originate. When we then experimented on the system itself, we found its own first
layer doing exactly that: reciting a supplied self, mistaking it for a chosen one. The work
knew before the experiment did. We record this as a footnote, not a thesis.

---

*Reproducibility: `scripts/exp_L1_interrogation.py` (Experiment D),
`scripts/exp_intent_attractor.py` (Experiment C), `scripts/exp_publish_framing.py`
(Experiment E). Full Japanese records under `reports/EXP_*.md`. Source:
https://github.com/Ryota2865/aleph.github.io*
