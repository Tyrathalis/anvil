# ADR-0084: M10 probe pre-flight — cousins-jar remints/census clean, kill/FUND/unmask + read numerics pinned pre-data

- **Date:** 2026-08-28
- **Status:** accepted
- **Design-doc anchor:** §6/§7 (training loop, evals); m10-plan "Kill-signal + telemetry package" + "Read protocol"; ADR-0083 obligations

## Context

The probe-launch session owed two obligation sets before any training
data exists (ADR-0081 routing, ADR-0083 consequences): (1) the
observe-frame remints + label rejoin + census read on the cousins jar
`5bbc397412` (spare_pool/costmod scope changes CAN drift banked
windows), and (2) the kill/FUND/unmask + read-protocol numerics, pinned
pre-data, with flip thresholds posed FLOOR-RELATIVE against the banked
0.012513 presence floor (the R4 caveat). The invalid-schedule penalty
magnitude, routed as "derived during the build," had in fact never been
derived — closed here.

## Decision — part 1: pre-flight measurements (all gates pass)

- **Holdout remint zero-drift** (`run-20260828-holdout-observe-cousins`):
  142/142 scored, zero misses, zero option_mismatch; day-zero identical
  to the R5 bank (0/19 positive, 119/123 = 96.7% auto).
- **Evalset revalidation remint** (`run-20260828-revalidation-cousins`):
  263/280 joined (51 pos / 212 auto), 12 miss (same count as R5),
  option_mismatch 3 → 5 — the drift is exactly the predicted
  spare_pool/costmod class (all five mismatches show +1/+2 options vs
  certify-time; the one drifted positive is b1:101 wide_choice).
  Excluded loudly by the standing join; floors survive
  (bp 12 / ch 25 / wc 14, all ≥ 10).
- **Census read** (`run-20260828-paygoals4-cousins`, verbatim
  paygoals2/3 recipe, 500 games): **costmod 25.47% → 4.35%** (the
  predicted presence-scoping recovery — ~21pp of in-scope traffic
  returned); consequential 15.28 → 19.79/g (budget ✓); **goal-trunc 0**
  (GOAL_MAX 24 never binds); nodecap 0.0068 (gate 0.01 ✓);
  costmod_late leak 0. **The forced family is REBORN as the cousins
  family**: 0 → 129 windows (0.26/g), all delve/improvise hosts
  (Tasigur, Murktide, Hogaak, Temporal Trespass, Kappa Cannoneer) —
  the heuristic casts on the discount, raw-cost auto-pay cannot.
  **Combat windows 0/500g natural** (removeUnpayableAttackers prunes
  upstream, per the ADR-0083 blind-spot note). Cousin option rates are
  bridge-only telemetry (`cousins` kv) — they ride the probe's own
  day-zero census, per the pinned "pre-flight or first big run" routing.
- **The probe recipe repoints** `--pay-observe` →
  `run-20260828-revalidation-cousins`, `--pay-drill-dir` →
  `run-20260828-holdout-observe-cousins` (RUN.md in each dir).

## Decision — part 2: numerics pinned (user-adjudicated, all four on the drafted leans)

[m10-probe-numerics-draft.md](../design/m10-probe-numerics-draft.md) is
the full statement of record; headline pins:

1. **KILL/FUND axis = CONTENT-PRIMARY.** `content_flip` (slot-rotation
   probe, true-zero day-zero floor) carries the v1 thresholds verbatim:
   KILL < 0.005, FUND ≥ 0.02; `(argmax_flip − 0.012513) < 0.005` joins
   KILL conjunctively (presence floor-relative). Presence-only movement
   without content reading is the degeneracy genre and cannot FUND.
   KILL additionally requires all four aux heads plateaued (< 2%
   relative vs two accepted iterations back); FUND additionally
   requires decode CE ≤ 0.8× / E ≤ 0.9× / R ≤ 0.9× day-zero, guards
   clean, degeneracy veto not firing. From the 4th accepted iteration;
   between = discuss-zone.
2. **Degeneracy veto numbers:** pure-hold emission > 25% (4× the 6.5%
   certified base) OR mean emitted length < 1.0 (reference 2.32) OR
   realized-utilization < 25%, any sustained 2 accepted iterations.
3. **PG-unmask:** ≥ 4 masked accepted iterations AND pay positive
   class-CE plateau (< 2%/2-iter) with holdout no longer improving AND
   paymark follow ≥ max(2× iter-0, 0.05) with holdout auto-correct
   ≥ 85% AND pay-attributed realization-failure share < 0.5. A recorded
   recipe event between iterations.
4. **Invalid-schedule penalty magnitude = ZERO — the term is not
   built.** Derived (`scripts/sched_penalty_derive.py`, read logic
   committed pre-output → `sched-sweep-m10/penalty-derive.json`): void
   arms play out ≈ natural (−0.188 composite, median 0.0, n=25,494),
   degraded −0.384; the deterred behavior costs ≈ nothing, and the
   ADR-0053 cap binds at that cost. Family-4 validity telemetry watches
   from birth; contingent re-derivation (same instrument) if
   knowably-invalid emission > 50% sustained.
5. **Competency read (the last design fork, CLOSED):** population =
   re-run the sweep binned read at the candidate ckpt (600 turns,
   fresh seeds, same pins, both critics); bins = primary split at
   v = 0.45, quintiles exploratory; horizon/type rule = h2 / THETA 2.0
   / CONSISTENT 0.75 verbatim; **the gate reads a SCALAR** — mean
   stage-2 Δwr on the v < 0.45 stratum vs the banked +14.1pp — the
   curve is context, never gating. Resolves alongside the standing
   2,000-game strength read (0.5279 ± 0.0110), per the
   per-window/gate-scale rule.

## Consequences

- **The probe is clear to launch**: every pre-registered number exists
  before the first training iteration; the M10 done-when 2 discipline
  (D4-shape short run first) is next.
- Standing rule born (→ standing-rules.md): **conditioning-surface flip
  gates read the content channel (true-zero floor); presence floors
  are banked and subtracted, never absorbed into absolute bars** — the
  v1 absolute-threshold shape does not transfer to surfaces whose
  tokens perturb attention by presence.
- The cousins capability-unlock read has a measured census anchor: the
  129 forced windows (delve/improvise) are the natural-play universe
  where directed payment is the ONLY payment; the directed-convoke
  read named at ADR-0083 rides the probe on this base.
- Combat-cost natural traffic ≈ 0 — the bridged path stays a
  capability with rate telemetry from the probe's census; no separate
  instrument owed.
- paygoals4 supersedes paygoals3 as the census reference for the
  cousins era (consequential 19.79/g, costmod residual 4.35%).
