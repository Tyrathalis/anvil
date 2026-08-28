# ADR-0080: M11-routing ceiling probes — BOTH RE-DEFER with their numbers (tutor/fetch 1.41pp/g, effect payments 0.69pp/g, vs the 2.2 bar); the effect-payment surface is real but the heuristic already captures it

- **Date:** 2026-08-27
- **Status:** accepted
- **Design-doc anchor:** [m11-routing-probes-spec.md](../design/m11-routing-probes-spec.md)
  (adjudicated 2026-08-26; launch pins pre-data at `5c0b307`); design-round
  obligation 6 ([m10-plan.md](../design/m10-plan.md)); ADR-0077 (the
  re-deferral condition this satisfies); ADR-0078 (the threshold scale)

## Question

Per-window and gate-scale ceiling value of (T) forcing the best
tutor/fetch target and (P) forcing pay/decline at resolution-effect
windows, vs natural heuristic play — routing M11, never gating M10's
build. Routing bar: gate-scale point ≥ 2.2pp/game ⇒ SCHEDULE; below ⇒
re-defer with the number.

## Instrument

The `-forcechoice` engine delta (fork `07c28fcf8a`) on the
m10-ceiling-census configuration: EXHAUSTIVE combined plan — 1,946
active-player-forkable points (T 796 / P 1,333, 183 shared), 6,718
forced arms, 67,880 game-end completions, K=8 target-turn-keyed paired
rolls, select/score split 0–3/4–7, iter-019 argmax server. 12 lanes,
~19h wall. Health CLEAN: crash 0.76% (the point-wipeout class, ADR'd
separately below), unended symmetric (0.41%/0.40%, no asymmetry flag),
fired rate 76.3% (above the 60% power assumption), 2 skips.

## Result — both probes below the bar

| probe | points used | Δwr/window [CI95] | gate-scale pp/g [CI-lo] | cov-disc | verdict |
| --- | --- | --- | --- | --- | --- |
| T tutor/fetch | 620/796 | +0.013 [−0.006, +0.030] | **1.41** [−0.63] | 1.21 | **RE-DEFER** |
| P effect payments | 922/1,333 | +0.004 [−0.006, +0.014] | **0.69** [−0.93] | 0.59 | **RE-DEFER** |

**The secondaries carry the understanding:**

- **T — no fixed-candidate policy helps:** every forced index pools to
  ≈0 vs natural (index 0: −0.22pp … index 5: +0.62pp; n≈3–5k each).
  The +1.3pp best-of read is residual noise and/or state-dependent
  selection — and even read as fully real, that selection competency
  is priced at 1.41pp/g central, under the bar. The heuristic's
  tutor/fetch choices are near-par with best-of-6-forced at gate
  resolution.
- **P — the surface is REAL and already captured:** force-decline
  costs **−2.5pp/window** (n=7,309) while force-pay ≈ natural
  (+0.1pp, n=7,314). Pay-or-suffer windows carry genuine 2.5pp-scale
  stakes, and natural play ≈ always-pay — the heuristic
  (`willPayUnlessCost`) already makes the right call. Headroom, not
  stakes, is what's absent. The cleanest possible re-deferral
  argument: measured value exists; it is already banked.

## Decision

1. **Tutor/fetch-target competency (§3d′ family 2): RE-DEFERRED with
   the number** (1.41pp/g [−0.63, +3.0-scale], per-arm flat). Any
   future scheduling argument must beat the state-dependent-selection
   pricing this probe measured — re-rankable at M11 scoping, not
   before.
2. **Resolution-effect payments: RE-DEFERRED with the number**
   (0.69pp/g; decline-cost 2.5pp/window already captured by the
   heuristic). **ADR-0077's condition — no second re-deferral without
   a measured argument — is SATISFIED**; the item leaves the
   must-measure queue and re-enters only on new evidence (e.g., an
   era whose policy stops paying correctly — the conditional holdout
   telemetry would show it).
3. Obligation 6 RESOLVED; the design round's measurement docket is
   complete.

## Consequences

- Assets: the `-forcechoice`/pay-decline instruments + `choice_pins/
  choice_plan/choice_read` (re-runnable at any era boundary — the
  probe is a label-mint-class asset like the sweep); the enriched-jar
  census stream from the lanes (src/api catalog) banked in the lane
  scratch files.
- Free finding for the M10 build: natural ≈ always-pay at
  pay-or-suffer windows is a measured behavioral fact of the era —
  a reference point for the supervised-conditional payment labels.
- The crash class surfaced by this run (0.76% of completions,
  point-shaped wipeouts, early-resume deaths — a GameCopier
  copy+resume defect candidate) is under active forensics (crash_why
  patch `7c4af49fa4`); routed to its own record when named — never
  a silent residual.
