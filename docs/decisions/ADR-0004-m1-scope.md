# ADR-0004: M1 scope — featurization line, tag rungs, deferred yield macros

- **Date:** 2026-07-04
- **Status:** accepted
- **Design-doc anchor:** §1–3 (encoder/state/policy), §6 phase 1, §9 (featurization, store); amends one sequencing line of [ADR-0003](ADR-0003-m0-closeout.md)

## Context

M1 planning surfaced decisions that shape the corpus — the expensive, hard-to-regenerate artifact. Two ledgered M0 facts force them: **replay drifts from in-run instances** (ADR-0003), so observations cannot be re-derived later and whatever is logged at generation time is what BC trains on; and the census proved the heuristic's **targets/X/modes/optional costs never surface as callbacks** (injected onto the SA), so an uninstrumented corpus carries no imitable cast labels. Full plan: [m1-bc-plan.md](../design/m1-bc-plan.md).

## Decision

1. **Featurization line refined** (§9's "featurize once, in Java" was written for the inference path): Java serializes a *versioned, structured, entity-level observation* (game-agnostic record envelope, §1 hygiene); tensor assembly (one-hots, dedup counts, embedding lookup) is a deterministic Python transform, run server-side at inference too. Feature iteration is free; only state-extraction changes force corpus regeneration.
2. **Labels for everything, heads for the rung:** the worker logs options + chosen answer for all live callbacks; BC scope is cut at model heads/realizers, not data. *Rung 1 (committed):* cast-composite priority (`CastPlan`) + M0 one-field tags (mulligan, triggers, binary, number). *Rung 2 (stretch):* combat constructs. Ordering and replacement/static families are M2-era in census-measured order. `CastPlan` splits into a **label extractor** (corpus prerequisite) and an **executor** (eval path; the 65%-veto-rate fix).
3. **Embedding model:** pin Qwen3-Embedding-4B (exact revision in run manifests), BGE-M3 as alternate in a pilot-corpus in-domain ablation. **Scryfall Tagger tags + LLM gap-filler deferred** (separate scrape project; ablation-addable later without regeneration).
4. **Corpus:** staged (≈50K-game pilot before the 500K run), overnight chunks as the planning assumption (~22–28 nights; daytime running and a cheap CPU-only VPS are upside/contingency, not schedule), meta-pool only on `cf2ca6ba` with personality randomization. Low-power decklist slices (precons) are a provenance-tagged later ablation, not a baseline blend; deck-power mix is not §6's skill-conditioning mechanism.
5. **Yield macros (§3b) move from M1 to M2** — amends ADR-0003's M1 main line. BC has no stop-setting labels; pseudo-labels would bake heuristic judgment into exactly the held-instant decisions §3b protects. The `yield_directive` protocol hook stays reserved.

## Consequences

- Observation schema + CastPlan label extractor become corpus-blocking deliverables; the pilot corpus is the schema-churn firewall (a schema miss after the full run costs ~a month of regeneration).
- Disk: corpus targets ~100–200GB compressed (inside §9's store budget; ~2TB raw, so per-game zstd is load-bearing; keyframe+delta is the fallback). The corpus is regenerable and needs no backup. Forward look: M2 self-play (1–3M games) is the only larger disk consumer (~0.5–1TB class) — retention/reservoir policy and dataset-boundary eviction manage it; checkpoints are tens of GB; everything else is noise.
- §15's BC-agreement row (high-80s, P=80%) now resolves against an honest metric: single-legal-option decisions excluded, per-tag reporting, pass-excluded priority agreement alongside raw.
- M2 inherits: combat constructs if rung 2 slips, yield-macro semantics, ordering/replacement families, loop-detector feature (needs engine-side detection), and the convoke/improvise callback-loop investigation.
