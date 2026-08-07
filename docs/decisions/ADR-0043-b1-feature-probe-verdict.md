# ADR-0043: B-1 derived-state feature probe — does NOT clear the gate; the trunk already encodes the arithmetic

- **Date:** 2026-08-07
- **Status:** accepted
- **Design-doc anchor:** §2 (state representation), §4 (value heads)
- **Inputs:** [ADR-0042](ADR-0042-d2b-design-session.md) (the pre-registered
  probe: ridge on `[STATE] ⊕ features` at the benchmark positions, gate =
  beat the 0.455 ridge / ~0.46 plateau), [ADR-0041](ADR-0041-extended-curve-path-verdict.md)
  (the frozen `frozen-probe-ext2-c2` benchmark + standing gate),
  `anvil/encoder/derived.py` (the feature module, DERIVED_VERSION 1),
  `scripts/feature_probe.py` (the harness),
  `data/runs/frozen-probe-ext2-c2/feature-probe-report.json` (numbers of
  record).

## Context

ADR-0042 B-1 bet that state-level arithmetic — race/lethality margins,
turns-to-death clock, castability-vs-mana, material/card-advantage
differentials, commander-tax state — was absent from the representation and
carried the missing live-vs-dead ranking signal. The probe is transform-side
and pure Python: 38 features in 5 families computed from the logged
full-state obs at the 6,117 benchmark positions (info-set-respecting,
leak-tested), ridge refit on `[STATE] ⊕ features` under the exact
frozen-probe split/CV.

## Findings (c2, holdout n=1,08x; state baseline reproduces 0.4552 exactly)

1. **No family clears the gate.** Best config `state+race` = **0.4597**
   (+0.0045 — inside the 0.43–0.46 plateau band and well inside holdout
   noise ~±0.03). `state+all` = 0.4357 (the 38 extra dims cost more than
   they add at this n). Leave-one-out drops ≈ 0 for every family.
   Robustness: extended alpha grid (3e3–1e5) only degrades; the
   frozen-probe MLP agrees (state 0.427, state+all 0.380 — nonlinearity
   doesn't rescue it).
2. **The features alone rank at 0.23–0.25** (linear = MLP), near the
   ADR-0036 critic floor (0.26–0.29) — the arithmetic predicts *something*,
   but everything it predicts is already in `[STATE]`.
3. **The sharp result — reconstruction:** `[STATE]` linearly decodes the
   derived features at **median R² 0.65**, and the highest-label-correlation
   features are the *best* encoded: lethal-margin-vs-self R² 0.94, life
   diff 0.88, turns-to-death 0.86–0.87, castability counts 0.80–0.89.
   **The arithmetic is not missing from the representation. The trunk
   carries it linearly and it does not carry the 0.46→0.94 residual.**
   ADR-0041's "representation-blind" is hereby sharpened: blind not to
   state arithmetic, but to whatever deeper structure separates
   winnable from dead — the thing rollouts see and no linear function of
   `[STATE]`-plus-arithmetic sees.
4. **En-route conditioning lesson (transform v2/v3, third sighting):**
   unclipped aggregates let infinite-combo boards (six-digit power) and
   drain kills (six-digit-negative life) own the feature std —
   standardization then crushes the normal-game range to ~0. Fixed at
   source: per-entity P/T contribution clipped to [0, 50], life to
   [-10, 150] (`derived.py` PT_CAP/LIFE_LO/LIFE_HI). The clip moved
   race-alone 0.21→0.23 and `state+race` +0.005 — real, and still nowhere
   near the gate. Standing rule: **any engineered aggregate gets a
   conditioning clip at birth, and a probe-side std sanity read.**

## Decision

1. **B-1 is out of the graduated run.** Per ADR-0042's aggressive-inclusion
   posture, only probe-cleared levers ride; no derived-feature family
   cleared. The feature module stays (leak-tested, cheap, and the probe
   harness reuses it for any future feature idea — the gate is now a
   one-command check: `feature_probe.py features` + `probe`).
2. **B-2 (partial-unfreeze ranking fine-tune) is the live lever** — the
   reconstruction result raises its prior: the signal deficit is not at
   the input, so pressure on the trunk's own weights (or, failing that,
   B-3 encoder work) is where the remaining probability mass sits.
3. If B-2 also fails its gate, B-3 unparks per ADR-0042 decision 1 — with
   this ADR as evidence that the encoder conversation starts at "what can
   the trunk not compute," not "what inputs is it missing."

## Consequences

- `frozen-probe-ext2-c2/` gains `derived-features.npz` +
  `feature-probe-report.json`; the benchmark stays frozen (same labels,
  same split).
- `tests/test_derived.py` (14 tests) pins feature semantics, the info-set
  leak invariant, statics-miss degradation, and the conditioning clips.
- Statics misses at the benchmark: 245/1,842 names, all token-class
  (Airbend copies, creature/Blood tokens) — graceful-degradation path
  verified in the dump meta.
