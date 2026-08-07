# ADR-0042: D2-B design session — probe-gated representation enrichment, aggressive inclusion, unfreeze in parallel

- **Date:** 2026-08-07
- **Status:** accepted (session decisions user-confirmed 2026-08-07)
- **Design-doc anchor:** §1 (card encoder), §2 (state representation),
  §4 (value heads), §3a/§3c (planning tiers + mana payment — priority
  note only, out of M6 scope)
- **Inputs:** [ADR-0041](ADR-0041-extended-curve-path-verdict.md) (the
  path-B verdict + the frozen benchmark gate),
  [ADR-0036](ADR-0036-d3-critic-calibration.md) (residual shape:
  winnable-labeled-dead, global), `frozen-probe-ext2-c2/` (the
  acceptance benchmark), [observation-schema-v1.md](../design/observation-schema-v1.md)
  (full-state records — the no-regeneration guarantee this ADR leans
  on), `anvil/encoder/cards.py` (the §1 fusion — already built).

## Context

Path B opened with a scoping requirement: no build before a design
session prices the options. Two archaeology facts reprice the space:

1. **The §1 card-encoder fusion already exists** (frozen text +
   structured card features + ID embedding → MLP). Card-static
   identity is not the open lever.
2. **Observations are full-state records**, designed so "feature
   iteration never forces corpus regeneration." State-level derived
   features are computed reader-side at transform time — **no dataset
   boundary, no fork delta, no corpus regeneration.**

What the evidence indicts is state-level arithmetic: the plateau lives
in ranking live-vs-dead, the ADR-0036 residual is global
(winnable-labeled-dead everywhere), and the missing distinctions —
race math, castability trajectory, material/card-advantage
differentials, clock — are aggregation arithmetic transformers learn
poorly from token soup without explicit features or targeted gradient
pressure. We have evidence both were absent: the outcome-label BCE
pressure at 833K steps never produced these circuits (linear probe
0.45 vs trained head 0.27 on the same vector), and no derived-state
features exist in the input.

## Decisions

1. **Two live options, both probe-gated on the frozen benchmark
   (beat 0.455 ridge / ~0.46 plateau on `frozen-probe-ext2-c2`,
   identical split), run IN PARALLEL** (user 2026-08-07):
   - **B-1 Derived-state feature enrichment (transform-side):**
     engineered per-player/global features computed from logged obs —
     initial families: race/lethality margins (on-board damage vs life
     over 1–2 turns), turns-to-death clock, castable-now/castable-next
     counts against mana development, material sums and
     card-advantage differentials, commander-zone/tax state. Probe =
     compute at the 6,117 benchmark positions, refit ridge on
     `[STATE] ⊕ features`; per-family deltas rank what carries the
     missing signal. Pure Python, no training, no boundary.
   - **B-2 Partial-unfreeze ranking fine-tune:** top-N trunk layers
     (sweep N) + value head, ranking-first loss on the benchmark's
     train split, game-grouped holdout read. A few GPU-hours per
     cell. The probe result prices the real build (which needs a
     value-tower split or partial-layer discipline to protect the
     shared policy trunk, and is era-scoped by construction).
   - **B-3 encoder swap stays PARKED** (§1 escape hatch) unless both
     probes fail their gate.
2. **Aggressive-inclusion posture (user 2026-08-07):** the M3→M5
   falsification record (five cycles, one promotion, every single-lever
   read expensive) justifies bundling. The probe layer IS the
   attribution discipline — each lever is measured independently
   against the frozen benchmark for near-zero cost — so **the
   graduated training run bundles every probe-cleared lever** rather
   than spending a run per lever. Run-level attribution discipline is
   preserved where it matters (D3 curriculum arm stays independent;
   the headline gate vs 0.5316 is unchanged).
3. **Graduated build feeds the shared trunk by default** (policy sees
   enrichment too, not a value-side fork): bigger blast radius,
   bigger upside, and the standing 2,000-game paired gate is the
   protection. A value-side-only fallback remains if the shared-trunk
   build destabilizes BC/serve parity.
4. **Boundary pricing recorded:** B-1 = none (transform-side, logged
   obs suffice; serve path recomputes the same features from live obs
   — loader-parity test extends to them). B-2 = no data boundary, but
   any unfrozen-trunk ckpt is a new era for era-scoped assets
   (isotonic maps, selection/evalset versions) per standing rules.
5. **Priority note (recorded, explicitly OUT of M6 scope):** planning
   (§3a tiers 2–3: wiring the `[PLAN]` emit-and-condition loop;
   pivotal-turn search over the now-battle-tested fork machinery) and
   conscious mana payment (§3c payment-class sub-head — filter lands
   are engine auto-payment misplays the model never sees) are **rising
   priorities**: the heuristic is heavily tuned but lacks planning
   capacity, so planning is the asymmetric edge the user expects
   out-performance to require. Dependency on file: tier-3 search
   scores leaves with the critic — a ranking-capable value signal
   (this milestone) is upstream on the critical path. Sequencing eval
   = future backlog item alongside.

## M6 D2-B done-when (refines m6-plan D2)

1. Both probes measured against the frozen benchmark; per-family /
   per-N results recorded.
2. If any lever clears the gate: bundled candidate built
   (transform + encoder plumbing + retrain recipe), mini-run
   validated, then the standing combined paired read vs **0.5316**.
3. If nothing clears: that is a result — B-3 unparks and gets its own
   pricing session; M6 closes honestly on the probe evidence either
   way.
