# ADR-0075: The window-rate sweep — 0.321 certifiable windows/game (~3× the mined bound), direct-measured conversion +9.2pp/window ⇒ perfect payment play ≈ +3.0pp/game; the supervised-conditional-signal M10 candidacy STANDS

- **Date:** 2026-08-24 (launched and resolved the same evening as the D6
  design session; both stages complete before midnight)
- **Status:** accepted
- **Design-doc anchor:** [ADR-0073](ADR-0073-m9-ceiling-measurement.md)
  decision 4 (the contingency this resolves); m9-plan "Window-rate sweep"
  addendum (pins PINNED pre-launch, committed `7558b21`);
  [m9-d6-plan-latent-spec.md](../design/m9-d6-plan-latent-spec.md) (the
  session that funded it, user decision)

## Question

ADR-0073 measured payment conversion but had only a mined lower bound for
the window RATE (0.112/g/seat — the top-ranked ~20% of the tagged
universe, under a miner ranking measured non-predictive). The gate-scale
arithmetic — and with it the M10 candidacy of the supervised-conditional-
signal attack — turned entirely on that unmeasured factor.

## Instrument

**Stage 1 (rate):** fresh in-era 500-game paytelemetry census on the
bundle jar (`run-20260824-ratesweep`, seed base 20500000, paygoals2's
deck pairs) → miner tags the universe (**5,076 windows, 10.15/game**) →
**uniform sample of 600** (rng 20260824) → h2 certification through the
unchanged standing instrument (shapes by the evalset priority rule).
**Stage 2 (direct conversion):** the 19 certified positives run to game
end — the sweep's own certification rows ARE the horizon-2 arm, because
identical job ids and seeds reproduce identical `rollSeed`s (the
ADR-0073 both-horizon pairing, at half cost by construction). Machinery:
`scripts/payment_rate_sweep.py` + `payment_certify.py` +
`payment_ceiling.py`, all unchanged where standing.

## Results

**Rate:** 19/600 = **3.17% [2.04, 4.89]** (Wilson 95) ⇒ **0.321 [0.207,
0.497] certifiable windows/game** — ~3× the mined bound. Executor
faithful at scale a third time: salvage 0.0000 on 15,128 directed rows.
123/600 windows read auto-correct (auto certifiably best), 581
failed-predicate — consequential windows are usually ties, as the D3
sparse-consequential premise said.

**Direct conversion (uniform population, fresh-certified):** paired
game-end win-diff **+9.21pp/window ± 4.26 (z = +2.16)**, 19/19 drills
faithful, zero unended rolls, **in-era recert 19/19 = 100%** — no
winner's-curse regression on same-day certifications, corroborating
ADR-0073's adjudication of its 44.6% guard fire. Spearman(margin,
win-diff) +0.359. Per-shape: wide_choice again carries the most value
(+15.6pp), blocker_pressure the least (+5.4pp); no phyrexian in the
frame (pool carries none without the hand-built decks — recorded frame
assumption, and the shape converts 0.0 anyway per ADR-0073).

**Completed gate-scale arithmetic:**

| conversion source | pp/window | × 0.321 w/g | vs ±1.1pp floor |
| --- | --- | --- | --- |
| borrowed central (ADR-0073 pooled) | +4.62 | +1.49 [+0.96, +2.29] | reaches |
| **direct (this sweep, stage 2)** | **+9.21** | **+2.96** | **~2.7× the floor** |
| borrowed upper (ADR-0073 recert) | +12.50 | +4.02 [+2.58, +6.21] | clears outright |

Honest precision note: the direct estimate's own CI is wide (n = 19
drills dominates; the joint rate×conversion lower bound approaches the
floor from above but does not clear it at 95%). The three-row bracket is
the honest statement: the point estimate sits mid-bracket at ~2.7× the
floor, and the pinned adjudication rule (below) was met on the
launch-time arithmetic before stage 2 sharpened it.

## Decision

1. **The pinned rule fires on the STANDS branch: M10 candidacy for the
   supervised-conditional-signal attack (ADR-0015 machinery) STANDS.**
   The upper-bound CI sits entirely above the floor; the direct
   measurement lands mid-bracket at ≈ +3.0pp/game.
2. **The ceiling story is now complete and reversed in one day:**
   ADR-0073's "sub-gate on every measured bound" was correct on the
   morning's bounds; the missing factor (rate) was ~3× the bound, and
   perfect payment play is worth ≈ +3pp/game — real at gate resolution.
   The M9 routing is UNCHANGED (payment = infrastructure, D6 = the
   promotion slot); what changes is the M10 scoping input the closeout
   carries.
3. **Recorded frame limits:** the rate is "certifiable by the standing
   shape taxonomy" (untagged consequential windows excluded — no
   predicate exists to certify them); one-seat mining convention; no
   phyrexian in the pool-derived frame. Each cuts the estimate LOW, so
   the +3.0pp/game reads as a floor of the taxonomy's value, not a
   ceiling of payment's.
4. `payment_ceiling.py`'s printed gate-arithmetic line still hardcodes
   the mined 0.112 rate — superseded by this sweep's measured 0.321 for
   any future read; parameterize on next touch (queue rider, not a
   mid-era change).

## Consequences

- **The M9 closeout ADR routes the payment-completion queue against a
  LIVE M10 candidate** with a measured ≈ +3pp/game ceiling — the
  no-silent-loss routing now has a number to weigh against §3b stops.
- The conditional-signal attack's shape sharpens: the model must FIND
  ~0.32 windows/game where deviation wins ≈ +9pp — precisely the
  supervised conditional-labeling problem ADR-0015's rollout-label
  machinery was built for (parked since M2).
- **Assets:** `scripts/payment_rate_sweep.py` (census-mirror gen +
  uniform sampler + rate read); `run-20260824-ratesweep/` (the tagged
  universe, 600-window adjudication, 19 game-end-labeled uniform
  positives — seed material for M10); the both-horizon-at-half-cost
  pattern (certification rows as the h2 arm via rollSeed identity).
