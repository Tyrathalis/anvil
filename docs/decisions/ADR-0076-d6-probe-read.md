# ADR-0076: the D6 plan-latent probe read — the mechanism VALIDATES (consumed in one iteration, FUND's letter met) and the v1 order-free target amplifies the interface-probing equilibrium at compounding speed; v1 is not promotion-funded, v2 (sequencing + resources) is the routed successor

- **Date:** 2026-08-25
- **Status:** accepted
- **Design-doc anchor:** [m9-d6-plan-latent-spec.md](../design/m9-d6-plan-latent-spec.md)
  (design + pre-registered gates + the two in-run amendments);
  [ADR-0074](ADR-0074-d6-r1-aux-target-probe.md) (the joint aux target);
  [ADR-0073](ADR-0073-m9-ceiling-measurement.md) decision 3 (the routing
  this executes); [ADR-0062](ADR-0062-m8-closeout.md) (the standing veto
  account the run re-confirmed through a new channel)

## The run

`d6-run20`, 2026-08-25: the D4-shape probe (8×480 planned) from
`d6-plan-init` (plan params at design init, pay params stripped —
pure-latent attribution). Three guard halts, each adjudicated same-day:

1. **i0, kl 0.080 (first attempt):** the consumption proj at lr 1e-3
   moved the policy off the behavior policy at ~100× recipe speed —
   with the aux MEASURE-ONLY (kl 0.0695 at the first flush, before
   w_plan calibrated). Amendment: split groups, proj 1e-4 / aux heads
   1e-3. Re-run accepted cleanly (kl 0.044).
2. **i1, veto 0.2768 > 1.5× (0.1815):** the knowability decomposition
   (`data/runs/veto-knowability-run20`, validity bars ≥ 0.98):
   first-attempt mana-relevant vetoes **1,381 → 2,838 (+105%)**,
   knowable fraction **0.559 → 0.615**, `generic_short` **+165%**,
   `timing` FELL. **The latent's first consumed behavior is amplified
   affordability probing through the veto channel** — ADR-0062's
   account through a new mechanism at ~10× drill-fed speed, ADR-0063's
   elevated-populations-are-more-knowable replicated. Amendment
   (user): veto guard 2.5× for the probe; veto trajectory promoted to
   a first-class secondary read. Re-evaluation accepted i1.
3. **i2, kl 0.080 again + veto 0.3788:** not the proj this time (rms
   0.0022, growing gently) — the policy itself reorganizing around the
   probing strategy: casts/g 41.1 → 38.4 → 36.8 (floor 32.9 ≈ one
   iteration away), argmax-flip FELL to 1.3% while behavior compounded
   (the plan-following absorbing into the trunk). **The veto secondary
   resolved: COMPOUNDS, does not saturate** — the run17/run19 runaway
   signature at iteration 2 instead of 10, under an already-loosened
   guard. **Probe CLOSED here (user decision)** — every pre-registered
   channel had resolved and continuing required loosening the kl guard
   that protects V-trace validity to watch a degenerate equilibrium
   deepen.

## The gate adjudication (spec §7 pins)

| channel | pin | result |
| --- | --- | --- |
| KILL (auto) | flip < 0.005 ∧ aux plateau, from accepted-iter 4 | **never fired — could not** (flip 6× its floor by i1) |
| FUND | flip ≥ 0.02 at an accepted iter, guards clean, aux BCE ≤ 0.568 | **letter MET at accepted i1** (flip 3.37%, BCE 0.0059, guards clean under the amended set) |
| aux | learnable? | **saturated**: BCE 0.7105 (day-zero) → 0.002 by i2 |
| reliance | day-zero 0.0 exact | i0 1.77% → i1 3.37% → i2 1.29% (absorption, see above) |
| veto secondary | saturate vs compound | **COMPOUNDS**: 0.18 → 0.28 → 0.38 |

**Adjudication: FUND's letter is met and its spirit is declined.** The
formulation is validated as a MECHANISM — consumed within one iteration,
behavior-moving at 10× the speed any prior lever showed, aux fully
learnable — and what it moves behavior TOWARD is the interface-probing
equilibrium, because the v1 target is an order-free action bag: the
cheapest way to satisfy "X happens this turn" is to attempt X at every
window and let the free veto oracle sort out when. Funding v1's 20-
iteration promotion run would train probing amplification. **No
promotion run on v1.**

## Decision

1. **D6 v1 RESOLVED: mechanism validated, formulation superseded.** The
   detached-carry architecture, serve carry, pass-0 loop mechanics, aux
   machinery, reliance instrument, and guard/kill wiring all carry
   forward unchanged; only the TARGET changes.
2. **v2 is the routed successor: sequencing + resources in the plan
   target** (spec ledger, user-endorsed): ordered/arrival-indexed
   actions + a resource-schedule component (end-of-turn
   untapped/floating, or affordability-at-execution — pulling the
   trunk's measured cost knowledge, D2a AUC 0.881, INTO the
   conditioning channel). Own R1-style offline probe before build (the
   ADR-0074 pattern; most machinery reusable).
3. **The unification framing goes to the M10 table** (spec ledger):
   turn planning and payment are one resource-scheduling competency;
   candidate M10 shape = schedule-bearing plan + re-advertised payment
   actuation + the ADR-0075 supervised conditional labels, read as one
   competency (the capabilities-over-fallback direction).
4. **M9 done-when 5 is now an open scoping decision, flagged for the
   closeout session:** (a) v2 redesign + probe + promotion run WITHIN
   M9 (extends the milestone), vs (b) close M9 on the probe verdicts
   (D4 negative, D6 mechanism-validated/formulation-superseded) with
   the promotion attempt moving to M10's unified competency. Not
   decided here.
5. **run20 stores are veto-elevated — never in a training mixture**
   (the run14/15/16 rule). Iteration dirs kept for the closeout's veto-
   trajectory figure; prune eligibility at the next stale-data pass.

## Standing rules born here

- **Price a conditioning channel's lr by its gradient DENSITY, not its
  init.** The starved-param arithmetic (ADR-0069) applies to heads fed
  by rare windows; an input projection fed dense PG at every carried
  window moves the policy at the lr you give it — 1e-3 was a 100×
  overdose the kl guard caught in 9 steps.
- **A guard-halt relaunch after a RECIPE change must clear the rejected
  phase's artifacts** (archive, don't delete). The resume machinery's
  phase-reuse is right for crashes and wrong for amendments — the first
  relaunch re-evaluated the old training output bit-identically.
- **An aux-target's SHAPE is a behavioral prior.** An order-free intent
  bag conditions every window toward attempting the intent NOW; what
  the latent is asked to predict is what the policy is nudged to
  enact. Target design is behavior design.
- **Falling reliance with compounding behavior = absorption, not
  disuse.** The flip metric measures the carry's MARGINAL effect;
  when the trunk internalizes the conditioned behavior, flip falls
  while the behavior persists. Read flip jointly with the behavioral
  series, never alone.

## Consequences

- The M9 closeout inherits: D4 negative + D6
  mechanism-validated/formulation-superseded + the veto-compounding
  read as the strongest evidence yet for the ADR-0062 interface
  account (a THIRD independent channel found the probing equilibrium,
  fastest of all). The payment-completion queue routing (ADR-0075's
  live M10 candidate) and the done-when-5 decision are the closeout's
  two open calls.
- **Assets carried:** the full plan machinery (model/serve/loop/tests,
  242 suite), `plan_reliance.py` + the day-zero bank,
  `veto-knowability-run20`, `d6-plan-init`, the amended launch recipe,
  monitor-row reliance series across 3 iterations.
- **Cost of the whole D6 build-and-probe arc: under two days**, three
  same-day guard adjudications included — the probe-first discipline
  priced exactly as intended.
