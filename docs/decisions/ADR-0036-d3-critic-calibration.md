# ADR-0036: M5 D3 resolution — critic calibration splits: absolute scale fixed by isotonic remap, ranking is representation-blind

- **Date:** 2026-08-05
- **Status:** accepted (measurement resolution; adoption scope below;
  milestone close remains user-gated)
- **Design-doc anchor:** §6/§7 (the "value function continuously
  audited against rollouts" invariant — mechanized here); resolves
  m5-plan.md D3 including the post-ADR-0035 residual-decomposition rider
- **Inputs:** ~3,750 banked K=8 rollout labels (cycle-1 map+sweep 1,879,
  cycle-2 map+sweep 1,871; zero trace-join misses), early_doom traces
  (per-turn critic values, both eras × {on-policy, d4-critic-fullvis}),
  evalset v2/v3 baseline re-measures (the repeat-noise floor),
  `scripts/critic_calibration.py` → `data/runs/critic-calibration-v1/`.

## Result — two findings, opposite signs

**1. Absolute calibration: FIXED (adopt).** The raw critic reads
0.57–0.59 where rollout truth is 0.22–0.27 (the 0.58-on-0.24 headline,
now confirmed on held-out games). A monotone isotonic remap, fit on an
80% game split, takes held-out ECE from 0.30–0.36 to **0.025–0.048**
(Brier 0.17–0.20 → 0.063–0.074), on both eras and both critics —
essentially the repeat-noise floor (paired re-measure sd 0.04–0.07).
The overconfidence was bookkeeping-level and is now correctable by a
lookup table.

**2. Ranking: NOT fixable by any calibration (the rider's reading 2).**
Held-out Spearman is **0.26–0.29** for every era × critic pairing —
and the achievable ceiling is **0.94–0.97** (Spearman between two
independent K=8 measurements of the same positions under the same
policy: c1 0.971, c2 0.943). Monotone remaps preserve ranking by
construction, so no calibration touches this. The post-remap residual
by ground-truth bin makes the blindness concrete: **winnable −0.56,
coin −0.30, long_shot −0.09, lost +0.16** — the calibrated critic
collapses the entire curated-loss population toward one value and
cannot separate live positions from dead ones. The failure is global,
not localized: worst-deck residuals are ±0.10–0.25 at n≈10 and turn
buckets are modest (t1–6 −0.14, later ≈0), so this is not another
commander-tax-style single-feature hole.

(Caveat recorded: grouping residuals by true bin conditions on label
noise, but with repeat-Spearman ≥0.94 the labels are close to E[wr];
the pattern is real. Implementation footnote: the Platt variant
diverged on one slice (c1/v_era) — Newton without damping; isotonic is
the adopted form and is unaffected.)

## Decisions

1. **Adopt the isotonic calibration map for cycle-3 curation and
   doom-labeling** — everything that consumes the critic's ABSOLUTE
   value (early_doom doom thresholds, ceiling estimates, addressable/
   luck-locked classification). Era-scoped like every other selection
   asset: each cycle fits its map from its own era's labels
   (the c1 and c2 maps differ in level — 0.584→0.224 vs 0.588→0.275 —
   consistent with the policy getting stronger).
2. **Ranking within loss-adjacent populations must come from rollouts,
   not the critic** — standing rule made explicit. The Grindstone
   pipeline already obeys it (selection bands are built on K-rollout
   labels; the sweep chose anchors empirically); this ADR is the
   measured justification.
3. **The rider verdict: representation, not calibration, is the deeper
   constraint.** The critic cannot rank exactly the population where
   ADR-0024 located the residual (near-tie/collapse windows) and where
   M5 located the non-compounding. A 0.27-vs-0.94 gap that survives
   perfect recalibration, globally across decks and turns, is the
   measured case that the frozen-encoder representation does not carry
   the live-vs-dead distinction. **Representation work (encoder
   enrichment / partial unfreeze, or rollout-label value targets that
   bypass the critic) is the measured M6 candidate** — arrived at by
   instrument reading, not vibes.
4. **The audit invariant is mechanized:** `critic_calibration.py`
   ingests any list of drills.jsonl dirs; every future map/sweep run
   appends to the calibration set by adding its dir to the era config.
5. **Ante correctness riders NOT triggered:** the adoption is
   curation-side only. The Ante ledger's variance-reduction terms are
   self-centering under monotone miscalibration of this kind; wiring
   the remap into Ante (and the carried draw-poison/re-deal items)
   moves to the M6 scope where any critic replacement lands.

## Consequences

- M5 done-when clause 3 is SATISFIED: measured, with a real adoption
  (isotonic map for cycle-3 curation/doom labels) AND the documented
  limit (ranking blindness) — both halves to held-out standard.
- All three M5 clauses are now resolved; the milestone close ADR
  awaits user confirmation per convention.
- The M6 shape suggested by M5's evidence chain: representation is the
  binding constraint (this ADR), curriculum composition is the proven
  cheap lever (ADR-0030/0031/0035), stock is not the problem
  (ADR-0035), and ~3,750 ground-truth labels + the parked ADR-0015
  rollout-label machinery are sitting there as a dense training signal
  that bypasses the blind critic entirely.
