# ADR-0038: M6 opening sequence — the representation question

- **Date:** 2026-08-05
- **Status:** accepted (structure user-agreed 2026-08-05 same session:
  probe-then-path shape, curriculum arm in scope, efficiency riders and
  disk pass folded in, pool expansion deferred)
- **Design-doc anchor:** §1 (card encoder), §4 (value heads / drill
  regime), §6 (Grindstone); seeds the M6 plan doc per the M1–M5 pattern
- **Inputs:** [ADR-0037](ADR-0037-m5-closeout.md) (closeout + scoping
  inputs), [ADR-0036](ADR-0036-d3-critic-calibration.md) (the ranking
  blindness measurement), [ADR-0035](ADR-0035-d2-compounding-read-resolution.md)
  (the one-shot verdict), [ADR-0015](ADR-0015-d4-closeout.md) (the
  parked rollout-label machinery + its stale economics),
  `data/runs/critic-calibration-v1/` (the 3,750-label set, zero
  trace-join misses), [ADR-0033](ADR-0033-m4-closeout.md) (carried fork
  inventory).

## Context

M5 ended with an unusually clean pointer. The drill loop is a one-shot
corrector per curation method (Δ2 = −0.58pp ± 0.73 vs Δ1 = +1.98pp ±
0.71), and the measured reason is representation: the critic ranks
loss-adjacent positions at Spearman 0.27 against a 0.94–0.97 achievable
ceiling, a gap that survives perfect recalibration and is global across
decks and turns. More of the same signal does not help; changing what
the gradient can see is the direction the M3→M5 falsification record
points at. Meanwhile ~3,750 K=8 rollout ground-truth labels sit banked
— a dense training signal that bypasses the blind critic entirely — and
the ADR-0015 rollout-label machinery is certified, priced (stale-ly),
and parked.

The fork in the road is whether the *frozen trunk features* carry the
live-vs-dead distinction and only the critic's outcome-label training
failed to extract it, or whether the representation itself is blind.
Those two worlds have very different costs, and one cheap experiment
separates them. M6 is built around running that experiment first and
committing to whichever path it opens.

## Decisions

1. **(User-agreed) The milestone question:** can we change what the
   gradient sees — and does that reopen improvement? Headline close =
   the standing 2,000-game combined paired read vs **0.5316**; either
   direction closes honestly with a decomposition.
2. **(User-agreed) D1 = the deciding probe, first:** fresh heads
   trained on the 3,750 banked K=8 labels against frozen trunk
   features.
   - Both trunks probed: the on-policy `iter-019` trunk (masked input)
     and `d4-critic-fullvis` (full-vis input, the curation instrument).
   - Per-era fit/eval (labels are policy-conditional), on the
     deterministic 80/20 game split `critic_calibration.py` already
     uses.
   - **False-negative guard:** ~3,000 training labels may be too few
     to learn ranking even if the features carry it, so the probe
     family includes sample-efficient members (ridge/linear, k-NN)
     alongside a small MLP, plus learning curves at 500/1,000/2,000/all
     — a "blind" verdict requires a *flat* curve, not just a low
     endpoint.
   - **Pre-registered readings:** held-out Spearman **≥ ~0.7 and
     rising** ⇒ the features carry it; the critic's outcome-label
     training was the problem ⇒ **path A** (rollout-label value
     targets: unpark ADR-0015, distill/replace the critic).
     **≤ ~0.4 and flat** across probes and curves ⇒ the representation
     is blind ⇒ **path B** (encoder enrichment / partial unfreeze).
     In between ⇒ price both, decide by cost.
3. **(User-agreed) D2 = the chosen path, built and gated.** Path A
   opens with a **labeling re-price**: ADR-0015's ~17 positions/h/worker
   was measured through a batch-1 server before micro-batching and the
   w=16 generation recipe existed; port the labeler onto both and
   re-bench before sizing any campaign (2–4× was already called
   plausible then). The **carried fork stability pass** (IndexOOB banked
   repro, targeting-retry forensics, MayPlay `.get(0)`, MinMaxBlocker
   realizer gap) is the pre-campaign gate, conditioned on path A — at
   campaign scale, hangs are throughput. Path B commits nothing until a
   dedicated design session scopes it (feature enrichment vs partial
   unfreeze vs §1 encoder-swap; dataset-boundary implications).
4. **(User-agreed) D3 = curriculum composition as an independent arm**
   (the proven cheap lever; winnable residual −5.1pp, and the −4.7pp
   conversion trade returned in run12). Recomposes selection v3 —
   still valid, since M5 promoted nothing — and runs as its own gated
   arm, never folded into D2: M5's value came from unconfounded deltas,
   and mixing the proven lever with the new-signal experiment would
   muddy attribution of both.
5. **(User-agreed) D4 riders:** isotonic-map wiring into the
   early_doom/curation tooling lands **early and unconditionally**
   (adopted era-scoped by ADR-0036 but not yet plumbed; any future
   curation depends on it). The Ante correctness items (draw-poison
   69% coverage, re-deal re-anchoring, node-level draw bias) ride any
   critic replacement, per ADR-0036 decision 5.
6. **(User-agreed) Opening chore — the disk pass:** ~150G of the 213G
   `data/runs` is six forensic dumps from closed runs whose questions
   all have closed ADRs (`d6-run2-i000/i005` 53G, `d6-run4-i000/i001`
   46G, `d6-run9-i002` 18G, `d6-run11-i011` 22G, `d6-run10-i007` 7.4G,
   plus `_bench_scratch` 889M and `_contaminated` 420M). Inventory each
   dir, confirm nothing ADR-referenced or calibration-feeding lives
   inside, produce a kill list for user sign-off, then delete or
   zstd-archive cold (user's choice at sign-off). Kept unconditionally:
   ckpts of record, every drills.jsonl dir (the calibration set grows
   from them forever), selection/evalset assets, baseline-era
   finalarm/confarm stores (the paired reads join against them), Ante
   certification records.
7. **(User-agreed) Pool expansion (new cards) is explicitly deferred**
   — and the probe doubles as its readiness evidence. Expansion rides
   on text-embedding generalization (§1), which is exactly the frozen
   representation under indictment; a path-B verdict is direct evidence
   the pool cannot safely grow yet. Adding cards now would also be a
   quasi-dataset-boundary event confounding every paired read in the
   milestone.
8. **(Recorded posture) In-loop efficiency work is closed by
   measurement, not neglect:** the serve path is a documented negative
   (ADR-0032: 0.05 ms Python-active; the ceiling is waiting), the
   generation-shape lever is harvested (w=16 + chunk clamp, ~+30%,
   standing recipe), the learner has its 4.7×. Iteration pipelining is
   rejected while the capability question is open (it is a recipe delta
   touching on-policyness — synchronous iterations were a deliberate M2
   choice), and eval thinning is rejected on the run12 seed-half lesson.
   The labeling path (decision 3) is the efficiency workstream with a
   guaranteed customer.
9. **(Carried rules)** Migration read gatekeeps any future cycle
   pricing; ranking-from-rollouts in loss-adjacent populations;
   era-scoped assets (selection/evalset/isotonic maps); combined paired
   read standard, fresh-seed tiebreaker on marginal t; drill mainlines
   never ingest; no tree edits during runs — serve/driver changes land
   between runs with mini-run validation; guards + watcher on every
   run; every run generates on fork `master` @ the current pin.

## Done-when (confirmed with the ADR)

1. **The frozen-trunk ranking probe is resolved** against the
   pre-registered readings — an ADR records the path verdict (A / B /
   priced-intermediate) with the learning-curve evidence.
2. **The chosen path's intervention is built and gated:** standing
   2,000-game combined paired read vs 0.5316 + evalset-v3
   decomposition; either direction closes honestly.
3. **The curriculum-composition arm is measured** as an independent
   run with its own gate read.
4. **Isotonic wiring is landed** in the curation/doom tooling; Ante
   riders landed or documented-deferred with the critic outcome.

## Consequences

- m6-plan.md is seeded from this ADR (drafted alongside).
- The M6 planning baseline is 0.5316 ± 0.0110; the probe's comparison
  constants are the 0.27 critic floor and the 0.94–0.97 repeat-measure
  ceiling.
- If path A lands, the eval/Ante critic lineage gets its first
  ground-truth-trained replacement and the §4 drill-regime value-target
  design gets its first live test. If path B lands, §1's encoder
  assumptions get their first measured revision — and the pool-expansion
  timeline inherits the answer either way.
