# ADR-0031: D3 experiment (a2) — rebalanced drill mixing clears the gate outside noise

Date: 2026-08-02
Status: accepted (promotion decision recorded below)
Context: M4 D3, d6-run11 (ADR-0030's bounded rebalanced run), evalset/selection v2.

## Result

d6-run11 (run10 recipe verbatim; only deltas: fresh seeds 20261031 +
`drill-selection-v2` with 18.8% ahead-positions) **completed all 20
iterations with zero guard halts** — the first drill-mixed run to finish
its schedule. The §6c pressure that halted run10 (drill rejection
density 1.65×, shaped-vs-masked drift) did not recur: rejection density
stayed flat all run, and the anomaly flag fired exactly once (iter 7)
without recurrence.

**Paired 2,000-game Ante-corrected reads, iter-019 vs the 0.5121
baseline ckpt (`d6-run7b/iter-014`):**

| seed set | iter-019 corrected | baseline corrected | paired Δ | t |
|---|---|---|---|---|
| 20260710 (standing) | 0.5316 ± 0.0110 | 0.5121 ± 0.0110 | +2.00pp ± 1.00 | 2.01 |
| 20260711 (fresh, confirmation) | 0.5585 ± 0.0110 | 0.5367 ± 0.0109 | +1.95pp ± 1.02 | 1.92 |
| **combined (3,994 paired games)** | — | — | **+1.98pp ± 0.71** | **2.77** |

The effect replicated at near-identical magnitude on an independent
seed set (the confirmation read measured BOTH ckpts fresh, sequential
matched load; both read ~+2.4pp higher raw on the new seeds — shared
seed-set luck the pairing removes). **Done-when #3 — a drill-signal run
beats the baseline outside noise — is SATISFIED.**

Attribution detail: vs its own init (run9-i009) the increment is
+0.80pp ± 1.01 (single seed set) — not independently significant, but
arithmetic-consistent (init +1.15 over baseline; 1.15 + 0.80 ≈ 2.00)
and corroborated by the mechanism below.

## Mechanism: the (a2) hypothesis held

Held-out evalset-v2 decomposition (paired vs the pinned policy's
re-measurement, D2.4 protocol):

| bin | iter-009 | iter-019 | run10 i015 (all-behind mixture) |
|---|---|---|---|
| lost | +2.8pp | **+7.5pp (t=2.4)** | +6.6pp |
| long_shot | +1.9pp | **+7.4pp (t=2.0)** | +6.7pp |
| coin | −2.9pp | −0.7pp | −0.7pp |
| winnable | −8.0pp | **−5.1pp (t=−2.9)** | −9.7pp |

Behind-play gains persisted at full strength on unseen positions; the
winnable regression **halved and shrank with dose** (−8.0 → −5.1
between iters 9 and 19) — the opposite of run10's dynamics, where it
deepened. Ahead-drills in the rotation actively repair conversion while
behind-drills keep teaching. Net at the drill pool: +3.9pp (run10: ~0).
ADR-0030's hypothesis — *the winnable regression was the balancing
term; fixing the mixture converts hard-position gains into net
strength* — is confirmed at full games.

Residual documented as a known trade: winnable −5.1pp (t=−2.9) has not
fully closed at 18.8% ahead-weight. Candidate levers if it matters
later: higher ahead fraction, or per-bin slice stratification. Not
license for another mixture-only run now.

## Decision

1. **Experiment (a2): resolved POSITIVE.** Drill-mixed generation at
   f=20% with a bin-balanced selection beats the baseline outside noise
   (combined t=2.77), replicated across independent seed sets.
2. **Promotion put to the user with this ADR:** `d6-run11/iter-019` as
   RL checkpoint of record, new baseline = its paired-read level
   (+1.98pp over 0.5121). Recommended: promote — the ADR-0023
   convention (outside-noise supersession ⇒ new ckpt of record)
   applies; the winnable residual is documented above.
   **RESOLVED (user, pending): ___**
3. Escalation (b) K-rollout advantage baselines: no longer armed by a
   negative — future escalation is opt-in for additional gains, not
   required by the ladder.

## Consequences

- Evalset v2 + per-game selection + bin-balanced holdout become the
  standing Grindstone curation pattern (whole-bin holdouts are
  retired for good).
- The mid-run decomposition driver phase (sketched 2026-08-02) and D4
  serving-path profiling proceed next while the GPU is free.
- If promoted: all future comparisons re-baseline on iter-019's reads;
  drill curation for future runs must regenerate from iter-019's own
  losses (the run9-i009-derived selection is stale against the new
  policy by construction).
- The confirmation-read pattern (fresh-seed paired re-read of both
  sides on a marginal t) worked and is cheap relative to a wrong
  promotion; adopt it as the standing tiebreaker for gate-adjacent
  reads.
