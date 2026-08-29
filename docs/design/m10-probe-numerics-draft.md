# M10 training-probe numerics — ADOPTED (user-adjudicated 2026-08-28, [ADR-0084](../decisions/ADR-0084-m10-probe-preflight.md))

Session: probe pre-flight. Structure was adjudicated 2026-08-26
(m10-plan "Kill-signal + telemetry package"); the numbers below were
adjudicated 2026-08-28, all four forks on the drafted leans
(content-primary flip axis / penalty zero / scalar read gate /
veto+unmask as drafted). This file is the full statement of record the
ADR points at; pinned PRE-DATA — no training iteration existed when it
was adopted.

Reference day-zero bank (`m10-sched-init/reliance-dayzero.json`, R6
re-bank on the cousins-era graft, 4,715 conditioned windows /
`m10-reliance-pop-20260827`):

| quantity | day-zero |
| --- | --- |
| argmax_flip (fed vs mask-closed) | **0.012513** (the presence floor) |
| content_flip (schedule A vs B) | **0.0 exact** (zero-init contract) |
| reliance_l1 | 0.786 (presence-driven) |
| decode aux CE | 2.6335 |
| E smooth-L1 | 0.5293 |
| R smooth-L1 | 1.7495 |
| pay positive class-CE / auto CE | 3.85 / 0.31 |
| pay holdout (`payment-holdout-v1`) | 0/19 pos, 96.7% auto |
| certified emitted-length reference | 0×11 / 1×29 / 2×35 / 3×70 / 4×25 (170; pure-hold base ≈ 6.5%, mean ≈ 2.32) |

## A. KILL / FUND (the v1 §7 template, floor-corrected)

**The floor-relative caveat resolves cleanly: the instrument already
separates the two channels.** `content_flip` (two different schedules
fed) has a TRUE-ZERO day-zero floor — v1's absolute thresholds carry
verbatim. `argmax_flip` (fed vs closed) carries the 0.0125 presence
floor — posed floor-relative. Content is the competency channel
(presence-only movement = "slots make me different" without reading
them — the degeneracy genre), so **content_flip is the primary axis**.

- **KILL** (driver-automatic, conjunctive, from the 4th accepted
  iteration, `SCHED-KILL` marker): max over accepted iterations of
  **content_flip < 0.005** AND **(argmax_flip − 0.012513) < 0.005**
  AND **all four aux heads plateaued** (< 2% relative improvement vs
  two accepted iterations back: decode CE, E, R, pay positive
  class-CE). Same 1-in-200 greedy-flip semantics as v1; both flip
  channels dead + nothing left to learn to say = the formulation is
  dead.
- **FUND** (human-adjudicated at the read, nothing auto-promotes):
  **content_flip ≥ 0.02** at any accepted iteration with guards clean,
  AND schedule-leg aux well below day-zero — **decode CE ≤ 0.8×
  (≤ 2.107)** and **E ≤ 0.9× (≤ 0.476), R ≤ 0.9× (≤ 1.575)** — AND the
  degeneracy veto (B) not firing. The pay leg deliberately does NOT
  gate FUND (it gates the unmask, C); the schedule leg carries the
  ceiling (ADR-0078).
- **Between = discuss-zone**, session adjudicates (the D4 pattern).
- Grounding: v1's 0.02 was ~half the D4 payment head's most-moved
  argmax shift, 20σ from floor at ~10k windows; at 4,715 windows
  binomial SE ≈ 0.002 — 0.02 is 10σ from the true-zero content floor.
  E gets 0.9× (not 0.8×) because 0.529 day-zero already sits on heavy
  slot-count regularity; same for R.

## B. Degeneracy veto (veto-shaped: blocks FUND, never kills)

Fires when EITHER holds over two consecutive accepted iterations:

- **pure-hold emission rate > 25%** (≈ 4× the 6.5% certified base), or
- **mean emitted schedule length < 1.0** slots (certified reference
  mean ≈ 2.32 — below 1.0 the surface has collapsed to
  near-hold-everything), or
- **scheduled-slot realized-utilization < 25%** (SchedServe
  follow/exec counters: realized slots / scheduled slots — schedules
  that exist but never bind are trivially "consistent").

Weak-but-honest signal (flip live, aux moving, emission shaped like
the reference) stays discuss-zone by construction.

## C. PG-unmask (fork-4 rider; a recorded recipe event between iterations)

All four, conjunctive:

1. **≥ 4 accepted iterations masked** (pinned 2026-08-26).
2. **Supervised pay leg converged, plateau-detector form**: positive
   class-CE relative improvement < 2% vs two accepted iterations back
   AND holdout positive class-accuracy (payment-holdout-v1, 19 pos) no
   longer improving (no net gain over the same window) — converged
   means "the labels are absorbed", not "a level was reached".
3. **Pay telemetry healthy**: marked-candidate follow rate
   (`sched_paymark_follow / (follow + deviate)`, the SchedServe
   counters) ≥ max(2× its iter-0 baseline, 0.05) (baseline recorded at
   launch — day-zero follow is ≈ 0 by the +2.0 auto init, so the 0.05
   floor is the operative bar), AND holdout auto-correct ≥ 85% (the D4
   guardrail carried).
4. **Payment not dominating realization failures**: pay-attributed
   share of realization-failure deviations < 0.5 at the latest
   accepted iteration.

## D. Invalid-schedule penalty magnitude — derived, and the derivation says ZERO

`scripts/sched_penalty_derive.py` on the banked h2 sweep lanes
(read logic committed before output; `sched-sweep-m10/penalty-derive.json`):

- **void arms ≈ inert**: paired composite vs natural −0.188 mean
  (median 0.0, n=25,494 rolls) — a fully-invalid schedule plays out
  ≈ as the natural policy.
- degraded rolls −0.384 vs clean rolls −1.377 (pooled, confounded the
  INSTRUCTIVE way: clean includes hold-alls; ambitious schedules
  degrade), within-arm contrast support nearly empty (16 mixed arms;
  degradation is arm-deterministic, not roll-random).
- The measured cost of the deterred behavior is **≲ 0.2–0.4 composite
  — an order below the 2.0 certification margin**, and the ADR-0053
  cap binds at that cost.

**Proposal: penalty magnitude 0 at the probe — the term is not built.**
The loop has no invalid-schedule penalty term today (§6c's
rejected-intent penalty is a different surface); the measurement says
there is ~nothing to deter (invalid emissions cost ≈ nothing — the
executor degrades gracefully and play continues). Family-4 validity
telemetry (knowably-invalid emission rate, per-slot afford-bit
calibration) watches from birth; if the probe shows runaway invalid
emission (knowably-invalid rate > 50% sustained), the penalty gets
re-derived AT that evidence with this script as the instrument. The
knowability gate + ADR-0053 rule stay pinned for that contingency.

## E. Read protocol (the one remaining design fork)

The standing 2,000-game paired read vs 0.5279 ± 0.0110 stays the
strength instrument, untouched. The competency instrument (the
LordOfThePigs binned-gain prototype, exploratory-reads §6):

- **Population**: re-run the sweep binned read at the candidate ckpt —
  the label-mint machinery re-run at SAMPLE_N 600 turns, fresh seeds,
  same recipe/pins (`schedule_sweep` + `schedule_explore2 binned`),
  both critics per the early_doom convention. The banked iter-019
  curve is the comparison baseline.
- **Bins**: primary split at **v = 0.45** (the measured conversion
  boundary: +14.1pp below vs +0.5pp above); era-critic quintiles kept
  as the exploratory curve (n≈30–38/bin is routing-signal resolution,
  not gate resolution — the reason the gate reads the split, not the
  quintiles).
- **Certification horizon / type rule**: h2 composite, THETA 2.0,
  CONSISTENT 0.75 — the sweep pins verbatim (no new type rule; the 1b
  h4 flag already resolved no-fire at ADR-0078).
- **Gate reads a SCALAR**: mean stage-2 Δwr on the v < 0.45 stratum,
  candidate vs the banked iter-019 +14.1pp (SE ≈ 3pp at n≈65
  positives). The curve itself is exploratory context, never gating.
  Claim resolution follows the standing per-window/gate-scale rule
  alongside the strength read.

## F. Not renegotiated here (standing, restated for the launch ADR)

- Schedule-token input projections in the 1e-4 group from first launch
  (run20 iter-0 class); veto-guard trips run the knowability
  decomposition before being treated as pathology.
- Probing-dissolution secondary read: veto-knowability v2 across the
  probe run — a read, never a guard.
- Probe shape: D4-genre short run (~5 accepted iterations) before any
  promotion-scale run; per-accepted-iteration reliance + counters +
  battery already wired (R4).
