# ADR-0034: M5 opening sequence — Grindstone cycle 2, the compounding question

- **Date:** 2026-08-03
- **Status:** proposed (core direction user-agreed 2026-08-03; structure
  drafted same session for confirmation at the next working session)
- **Design-doc anchor:** §6 (Grindstone); seeds the M5 plan doc per the
  M1–M4 pattern
- **Inputs:** [ADR-0033](ADR-0033-m4-closeout.md) (closeout + carried
  inventory), [ADR-0031](ADR-0031-a2-resolution.md) (the cycle-1 win +
  curation-staleness rule), [ADR-0030](ADR-0030-d3-experiment-a-resolution.md)
  (the curriculum-composition mechanism), [ADR-0032](ADR-0032-d4-serving-path-resolution.md)
  (the w=16 recipe), `data/runs/run11-i019-finalarm-s{0,1}` (cycle-2
  curation substrate, verified present), `drill-map-r9i9-k8/` +
  `drill-sweep-lost-20260729/` (~1,900 K-rollout ground-truth labels =
  the critic calibration set).

## Context

M4 proved the drill loop works once: one full
curate → map → sweep → select → mix → gate cycle produced +1.98pp
outside noise. The obvious and unresolved question is whether it
*compounds* — and the window to answer it cheaply is now, before any
other direction (pool growth, expressiveness, escalation (b)) makes
checkpoints less comparable across passes.

**The hypothesis under test (user's framing, recorded at M4 close):**
fixing bad decisions moves the performance-collapse points to a higher
level; training on the *new* collapse points narrows toward a higher
level of play. The drill loop as a ratchet, not a one-shot correction.
The alternative it competes with: cycle 1 harvested a fixed stock of
correctable errors, and a second pass re-finds mostly the same
residue (luck-locked + already-fixed) — a one-time correction dressed
as a curriculum.

Two structural facts shape the design:

1. **The cycle-over-cycle curation comparison is itself evidence.**
   Before any training, cycle-2 curation on iter-019's own losses
   yields directly comparable profile numbers (addressable fraction,
   luck-locked share, collapse-turn/peak-value distributions, overlap
   of colliding decks) against cycle 1's 584-loss profile — the
   "collapse points moved up-level" claim is measurable at the
   curation stage, cheaply, and predicts the training outcome.
2. **The compounding read demands a near-verbatim run.** Every recipe
   delta between cycles confounds Δ2-vs-Δ1. The only accepted deltas:
   selection/evalset v3 (forced by the staleness rule), init/mainline
   pin = iter-019 (forced by promotion), w=16 generation (ADR-0032,
   throughput-only by construction), fresh seeds. The winnable-residual
   levers (higher ahead-weight, per-bin slice stratification) are
   explicitly NOT folded into cycle 2 — they would make a slope
   reading uninterpretable.

## Decisions

1. **(User-agreed) M5 = Grindstone cycle 2, now,** for cross-pass
   comparability; the headline deliverable is the slope: Δ2 (cycle-2
   gate read vs 0.5316) against Δ1 (+1.98pp ± 0.71).
2. **(User-agreed) The compounding hypothesis is the milestone
   question** — both resolutions are acceptable closes: a ratchet
   verdict (keep cycling, price the next pass) or a diminishing/flat
   verdict with the mechanism decomposed (curation profile vs held-out
   transfer vs conversion trade).
3. **(Proposed) One promoted secondary: critic calibration.** The
   ~1,900 K-rollout ground-truth labels are a free calibration set
   against a critic that reads 0.58 where ground truth is 0.24.
   Bounded deliverable: a calibration pass measured on held-out
   labels; adopt for cycle-3 curation/eval on improvement, documented
   negative otherwise. It does NOT touch cycle 2 (decision 2's
   verbatim discipline). The M4-carried Ante correctness riders
   (draw-poison coverage, re-deal re-anchoring) ride this deliverable
   if it lands.
4. **(Proposed) Cycle-2 curation runs the cycle-1 method verbatim**
   (same early_doom parameters, same two-critic cross-check shape,
   same K=8 map + anchor sweep + per-game in-band selection + ~⅓
   bin-balanced evalset holdout) so the profile comparison in Context
   fact 1 is method-clean.
5. **(Proposed) Escalation (b) stays parked** unless the cycle-2 read
   resolves flat AND the decomposition indicts signal quality rather
   than curriculum stock — the one case where per-position advantage
   variance is again the binding constraint.
6. **(Carried rules)** w=16 recipe (ADR-0032); drill mainlines never
   ingest; D2.4 re-measurement pairing; fresh-seed confirmation on
   marginal t; promotion on cleared gate (user standing posture);
   every run generates on fork `master` @ the current pin; guards +
   watcher on every run.

## Done-when (draft)

1. **Cycle-2 curation/selection/evalset v3 online** with the
   cycle-over-cycle profile comparison recorded (the collapse-point
   migration read) — an ADR or plan section states whether collapse
   points moved and how the addressable stock changed.
2. **The cycle-2 run's compounding read is resolved:** standing
   2,000-game paired gate vs 0.5316 (fresh-seed confirmation if
   marginal) + evalset-v3 decomposition; the closing ADR records Δ2
   vs Δ1 and the slope verdict, whichever way it goes.
3. **Critic calibration measured:** adopted for cycle-3 use on
   demonstrated held-out improvement, or documented negative.

## Consequences

- m5-plan.md is seeded from this ADR (drafted alongside).
- The M5 planning baseline is 0.5316 ± 0.0110; Δ1 = +1.98pp ± 0.71 is
  the comparison constant.
- If decision 3's calibration lands, the eval/Ante critic lineage gets
  its first ground-truth-anchored correction — a precedent for
  auditing the critic against rollouts continuously (design invariant
  "the value function is continuously audited against rollouts"
  becomes mechanized rather than aspirational).
