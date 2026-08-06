# ADR-0039: M6 D1 resolution — the frozen-trunk ranking probe reads INTERMEDIATE (rising, sample-limited)

- **Date:** 2026-08-05
- **Status:** accepted (pre-registered verdict is mechanical; the
  post-pricing path commitment remains the user's, per ADR-0038)
- **Design-doc anchor:** §1 (card encoder), §4 (value heads), §6
  (Grindstone)
- **Inputs:** [ADR-0038](ADR-0038-m6-opening-sequence.md) (the
  pre-registered readings), [ADR-0036](ADR-0036-d3-critic-calibration.md)
  (the floor and ceiling constants),
  `data/runs/critic-calibration-v1/dataset.jsonl` (the 3,750-label
  substrate), `scripts/frozen_probe.py` (the instrument, built this
  session), `data/runs/frozen-probe-v1/` (features + probe-report.json).

## Question

Can anything learn to rank the 3,750 banked K=8 rollout labels from
frozen trunk features? Pre-registered readings (ADR-0038 / m6-plan D1):
held-out Spearman ≥ ~0.7 and rising ⇒ path A (rollout-label value
work); ≤ ~0.4 and flat ⇒ path B (encoder work); between ⇒ record the
curve shapes and price both.

## Method (as pre-registered, no deviations)

- **Features:** frozen `[STATE]` read-out (d=512 — the exact vector the
  value head consumes) captured at each labeled position from BOTH
  trunks: `d6-run11/iter-019/train` (the policy trunk of record, masked
  windows) and `d4-critic-fullvis` (full-vis windows, the curation
  instrument). Window assembly = the Ante `ValueEvaluator` verbatim;
  position pairing = the early-doom first-obs-carrying-decision-of-turn
  convention the labels were banked under. 3,750 labels → 2,835 unique
  positions, **zero join misses**; join validated by re-deriving the
  banked `v_d4` column through the d4 value head (mean |Δ| 0.002, max
  0.013 — bf16 batch-composition noise, no outliers).
- **Probes:** ridge (closed-form) + k-NN (cosine) + 2-layer MLP (256
  hidden, early-stopped), hyperparameters by 5-fold game-grouped CV on
  the training split only. Same deterministic 80/20 game split as
  `critic_calibration.py`; per-era fits (rollout truth is
  policy-conditional). Learning curves at 500 / 1K / 2K / all — note
  **the 2K point is unreachable within an era** (~1.44–1.48K training
  labels/era after the game-level holdout), so the realized curve is
  500 → 1K → ~1.5K.
- **Baseline reproduction:** the banked critic columns re-scored on
  this exact split give Spearman 0.258–0.295 — the ADR-0036 floor
  reproduces, so the harness is consistent with the measurement under
  indictment.

## Result

Held-out Spearman (best probe per cell at full size; `probe-report.json`
has every cell):

| era | trunk | 500 | 1K | all (~1.5K) | best probe |
|---|---|---|---|---|---|
| c1 | policy-i019 | 0.359 | 0.389 | **0.395** | MLP (ridge 0.365) |
| c1 | d4-critic-fullvis | 0.302 | 0.336 | **0.336** | MLP ≈ ridge |
| c2 | policy-i019 | 0.403 | 0.413 | **0.455** | ridge (MLP 0.430) |
| c2 | d4-critic-fullvis | 0.352 | 0.328 | **0.356** | MLP |

Constants for comparison: critic floor 0.26–0.29 (reproduced in-run),
repeat-measure ceiling 0.94–0.97.

Supplementary (full size, for pricing): concatenating both trunks does
NOT beat the best single trunk (c2 ridge 0.439 vs 0.455 policy-alone;
c1 0.353 vs 0.395) — the two trunks are largely redundant. Adding the
`[PLAN]` latent to `[STATE]` also adds nothing (c2 0.381). Ridge picked
the heaviest alpha (1000) in every cell — the sample-limited regime's
signature.

## Verdict: INTERMEDIATE (the pre-registered "between" reading)

1. **Not path A as it stands.** No probe, trunk, era, or feature
   combination approaches 0.7. The frozen features do not demonstrably
   carry live-vs-dead at the strength path A's premise requires.
2. **Not a path B conviction either.** The curves are **rising, not
   flat** (c2/policy 0.403 → 0.413 → 0.455; c1/policy 0.359 → 0.389 →
   0.395), and every probe beats the critic floor by +0.08–0.18 — a
   linear read of the frozen `[STATE]` vector extracts more ranking
   signal than the critic's own trained value head. The small-N
   false-negative guard fired exactly as designed: a "blind" verdict
   requires flat curves, and we do not have flat curves at ~1.5K
   labels/era.
3. **Findings that inform pricing either way:**
   - The **policy trunk out-ranks the full-vis critic trunk in both
     eras** (0.395/0.455 vs 0.336/0.356). Visibility is not where the
     ranking signal lives; if a distilled ranking head is ever built,
     the policy trunk is the substrate to beat.
   - The critic's outcome-label training demonstrably left signal on
     the table (floor 0.27 vs linear-probe 0.45 on the same vector) —
     ADR-0036's "representation-level blindness" was partly *head*
     blindness. But 0.45 vs a 0.94 ceiling means most of the distance
     is still unexplained: either feature truncation (path B's world)
     or label starvation (path A's world). The probe cannot separate
     those at this label count — by construction, only more labels can.

## Consequence (per the pre-registered "between" procedure)

- **The D2-A labeling re-price runs FIRST** — m6-plan D1.4 explicitly
  sanctions this ordering ("the one legitimate reason to run the
  re-price before the path verdict"). It is cheap, has a guaranteed
  customer regardless of path, and its output prices the deciding
  follow-up: a label-expansion tranche (order 5–10K labels/era) to
  extend the learning curve where it is still rising.
- **The path commitment waits for the extended curve.** If it keeps
  rising toward ~0.7, path A's premise strengthens (and the tranche is
  already the first batch of path A's training set); if it flattens in
  the 0.4–0.5 band, that IS the flat-curve evidence path B's verdict
  was missing, at a label count where the guard no longer protests.
- **Curriculum arm (D3) is unaffected** and can run in parallel — it
  needs nothing from this verdict.
- Probe instrument (`scripts/frozen_probe.py`) and the feature dump
  (`data/runs/frozen-probe-v1/`) are era-scoped assets: features are
  ckpt-frozen by construction and the dump records its trunk paths.

## Standing-rule note

The probe adds a corollary to ranking-from-rollouts (ADR-0036): the
floor-vs-probe gap (0.27 vs 0.45 on the same frozen vector) means
**value-head scores understate what the trunk knows** — any future
"can the model see X?" question should be asked with a probe on
`[STATE]`, not by reading the trained head.
