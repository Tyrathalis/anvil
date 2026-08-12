# ADR-0053: Sequence probe resolved — contrastive signal is real, compounds with horizon, and reaches label-grade at N=4

- **Date:** 2026-08-11
- **Status:** accepted
- **Design-doc anchor:** §6 (contrastive pairs), §3a (planning), m7-plan D2 routing pin

## Context

The D2 routing pin (user-approved 2026-08-11) put a sequence-contrastive
probe first: after ADR-0051 falsified natural-variation labels and
ADR-0052 falsified per-decision forced-branch Δwr labels at any
affordable K, the open question was whether contrastive signal exists at
*sequence* granularity — the axis both ADR-0049 (timing, not choice) and
ADR-0052 (SD pure-noise at single decisions) pointed to.

Instrument: the forced-branch harness extended with a persistent
directive over an N-turn horizon (fork `6d2f44c9d3`, `-forceseq <n>`) —
three arms per drilled fork point sharing rollSeeds per (fp, r):
NATURAL (no directive), HOLD-N (force-pass every bridged priority cast
window for N turns), ACT-N (`forbid_decline` every window; exhaustion
degrades to pass, counted). Population: the 61 corrected in-band points
(ADR-0052's true-winrate band at crash−2, both stores). Analyzer:
`scripts/seq_probe_read.py`, the ADR-0051/0052 variance decomposition
per pairwise contrast.

## What was measured

Three rungs (N=2/K=16 same-day, then N∈{2,4} at K=32), 61 points each,
triples ≥ 99.9%, crashes ≤ 2/1952, zero directive anomalies. Pooled:

| contrast | N=2 K=16 | N=2 K=32 | N=4 K=32 |
| --- | --- | --- | --- |
| hold − nat: mean | −2.6pp (t −2.02) | −2.6pp (t −2.46) | **−6.1pp (t −4.49)** |
| hold − nat: var ratio / RMS true | 1.33 / 0.049 | 1.88 / 0.057 | **3.73 / 0.090** |
| act − nat: mean | −0.9pp (n.s.) | +0.1pp (n.s.) | −1.7pp (t −2.29) |
| act − hold: mean | +1.6pp (n.s.) | +2.7pp (t +3.14) | **+4.4pp (t +3.47)** |
| act − hold: var ratio / RMS true | 0.83 / 0 | 1.20 / 0.027 | **3.79 / 0.085** |

1. **Deferral cost compounds with horizon:** −2.6pp over 2 turns →
   −6.1pp over 4 (≈ −1.5pp per held turn), near-uniform (27 of 28
   nonzero points negative at N=4). Replicated across K rungs (identical
   −2.6pp at K=16 and K=32) and sign-replicated across stores. Causal,
   engine-adjudicated: at contested mid-game states, holding casts loses
   games. C3 (§6c economy re-tune) is now doubly evidenced — the dense
   penalty trained precisely this behavior (ADR-0049's cast-suppression).
2. **Per-point heterogeneity grows with horizon and reaches the
   pre-registered 0.10 label pin:** RMS true Δwr 0.049 → 0.057 → 0.090
   (hold−nat), 0.085 (act−hold), var ratios 3.7+ at N=4 (decisively
   above noise on 60 df). Single decisions carried zero resolvable
   signal; 4-turn plans carry label-grade signal. **Plan-granularity
   credit is the confirmed axis.**
3. **Timing characterization of iter-019:** natural ≈ forced-greedy at
   N=2; natural > forced-greedy at N=4 (−1.7pp) — the policy's timing
   has real value that pure aggression destroys, while excess holding
   destroys far more. Ordering: natural > greedy ≫ hold.
4. **Campaign economics:** the trainable contrast is act−hold (both arms
   forced; no natural arm needed) ⇒ 2 arms × K=32 = 64 completions per
   point at N=4. Coverage funnel per ADR-0052 (~96% fire × ~33–40%
   model-seat-active) stands.

## Decision

1. **The C bundle is funded.** No further rungs — N=4 sits at the pin
   and horizon becomes a campaign hyperparameter. Next: the design round
   for sequence-contrastive training targets (act−hold advantages at
   drilled points, N≈4) bundled with C2a (corrected-map value targets)
   and C3 (§6c re-tune), then the D3 stability pass + era boundary +
   re-baseline, then one training run against the standing paired gate
   (m7-plan done-when 2/3).
2. The probe instrument (persistent-directive forced branch) is a
   standing asset: it is §6's contrastive-pair generator at sequence
   granularity and the natural substrate for §3a plan-segment credit.

## Consequences

- M7's central hypothesis is alive in sharpened form: dense per-decision
  signal does not exist (0051, 0052), dense per-PLAN signal does — the
  training-target design must credit decision sequences, not decisions.
- The −1.5pp-per-held-turn number gives C3's re-tune a calibration
  target: the §6c penalty must never exceed the measured cost of the
  passivity it deters.
- The act−nat N=4 result (−1.7pp) cautions against pure-aggression
  training targets: the label should reward *realized best cast vs
  deferral*, not aggression per se.
- Design round inputs carried: target shape (per-point advantage vs
  binary preference), mixing weight vs the sparse terminal signal,
  whether targets ride policy-gradient or an auxiliary head, and the
  N-horizon/K budget per campaign point (64 completions/point at
  N=4/K=32 measured here).
