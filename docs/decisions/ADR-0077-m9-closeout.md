# ADR-0077: M9 closeout — the interface round closes on its probe verdicts; no promotion run; the mechanism verdict is FALSIFIED; M10 charters the unified resource-scheduling competency

- **Date:** 2026-08-25
- **Status:** accepted (user decision, closeout session)
- **Design-doc anchor:** [m9-plan.md](../design/m9-plan.md) (done-when 5
  and 6); [m9-d6-plan-latent-spec.md](../design/m9-d6-plan-latent-spec.md)
  (the v2 direction + the unification framing, both user-pinned
  2026-08-25); [ADR-0062](ADR-0062-m8-closeout.md) (the prediction this
  milestone falsified)

## What M9 asked and what it answered

M9 opened (2026-08-19) as **the interface round**: give the model a
conscious mana-payment surface (§3c), with ADR-0062's veto-collapse
prediction as the falsifiable mechanism check. Six days later every
question the milestone could resolve is resolved:

- **The mechanism verdict: FALSIFIED** (done-when 6's hard half,
  resolved 2026-08-23 by the `d6-run19` control,
  [ADR-0072](ADR-0072-d4-control-run-veto-collapse-falsified.md)).
  With the campaign restored and §3c on, vetoes did not collapse
  (kvr −3.7%, CIs overlapping; slope −0.00008, inside the drill-fed
  band) and the surface bought no stability (guard halt one iteration
  EARLIER than the §3c-off run17). run18's decline was the missing
  campaign, not the surface. ADR-0062 made falsification explicitly
  first-class; this is that outcome, recorded as such.
- **The standing veto account is stronger than ever.** Three
  independent channels now find the same equilibrium: drill-fed
  training runs (M8, run17), the §3c-on control (run19), and the
  plan-latent conditioning channel (run20 — veto 0.18→0.28→0.38 in
  three iterations, ~10× drill-fed speed,
  [ADR-0076](ADR-0076-d6-probe-read.md)). Under auto-payment the veto
  channel is the model's only affordability oracle, and every training
  signal that raises attempt-priors routes through it.
- **The payment capability negative, replicated:** the §3c head never
  acquired conditional discrimination — run18 pooled z=+0.75
  ([ADR-0069](ADR-0069-d4-read-adjudication.md)), run19 selectivity
  1.19 at 2× head dose ([ADR-0072](ADR-0072-d4-control-run-veto-collapse-falsified.md)).
- **The value question, measured instead of assumed:** the certify
  proxy CONVERTS where it holds (+12.5pp/window, Spearman +0.465,
  [ADR-0073](ADR-0073-m9-ceiling-measurement.md)), the aggregate
  mined-window ceiling is sub-gate — and the uniform rate sweep
  ([ADR-0075](ADR-0075-window-rate-sweep.md)) showed the mined bound
  was ~3× low: **perfect payment play ≈ +2.96pp/game, ~2.7× the gate
  floor**. Real at gate resolution, reachable as a supervised
  conditional competency, not by the marginal-signal path two runs
  disproved.
- **The plan-latent mechanism VALIDATES** ([ADR-0076](ADR-0076-d6-probe-read.md)):
  detached carry + dense aux is consumed within one iteration
  (argmax-flip 3.37% at accepted i1, aux BCE 0.7105→0.002, day-zero
  bit-identity exact) — the fastest behavior-moving lever the project
  has measured. And the v1 order-free target's SHAPE trains
  interface-probing, so v1 was not promotion-funded.

## Done-when 5: resolved as SUPERSEDED, with reason (user decision)

The clause demanded one full training run closed by the 2,000-game
combined paired read. **No such run closed in M9, and the milestone's
own measurements made running one unjustifiable on every branch:**

1. **D5 payment full run:** ADR-0073 measured the mined-window
   aggregate ceiling sub-gate, and ADR-0069/0072 showed the marginal
   training path acquires no conditional selectivity. The funded
   version of payment strength is ADR-0075's supervised conditional
   competency — an M10 build, not a rerun of a disproven recipe.
2. **D6 v1 promotion run:** ADR-0076's adjudication — FUND's letter
   met, spirit declined. Twenty iterations would have trained probing
   amplification.
3. **D6 v2 within M9:** v2's coherent experiment is the one the
   unification framing names — schedule-bearing plan target + payment
   actuation + the ADR-0075 conditional labels, trained and read as
   ONE competency. Running v2-alone inside M9 rebuilds the
   split-across-surfaces defect the framing identifies, and would
   violate the M9-born standing rule *measure the ceiling before
   building the learner* (planning's ceiling is unmeasured; doing it
   properly makes M9 a second milestone wearing the same number).

**The strength verdict on record: no promotion. Ckpt of record stays
`d6-run11/iter-019`; the post-boundary baseline stands at
0.5279 ± 0.0110 (ADR-0068 re-pin).**

## The veto trajectory, consolidated (the figure ADR-0076 owed)

| run | §3c | campaign | conditioning | veto trajectory | halt |
| --- | --- | --- | --- | --- | --- |
| run17 (M8) | off | drill-fed | — | slow climb to 0.303 (>1.5× i0) | i11 |
| run18 (D4) | on | none | — | kvr −33% (campaign missing, not collapse) | ran 8 clean |
| run19 (control) | on | restored | — | flat (kvr −3.7%, CIs overlap), guard halt | i10 |
| run20 (D6 v1) | off | run19 recipe | plan latent | 0.181 → 0.277 → 0.379 under a 2.5× guard | i2 |

Same equilibrium, three channels, and the conditioning channel reaches
it an order of magnitude faster than drill pressure. This table is the
closeout's veto-trajectory record; the run20 iteration stores it was
held for are now prune-eligible (kill list below).

## M10 routing

1. **M10 headline charter: the unified resource-scheduling
   competency** (user framing, spec ledger 2026-08-25). Turn planning
   and payment are one competency — within-turn resource scheduling —
   split across two surfaces by our architecture. Candidate shape:
   the v2 schedule-bearing plan target (sequencing + resources,
   pulling D2a's measured cost knowledge into the conditioning
   channel) + re-advertised payment actuation
   (capabilities-over-fallback) + the ADR-0075 supervised conditional
   labels, trained and READ as one competency. The v2 offline target
   probe (ADR-0074 pattern) runs INSIDE M10's design round, so the
   target is co-designed with the actuation surface, not pinned
   before it.
2. **§3b learnable stops** stays a named M10-scoping candidate (the
   M8/M9 carry) — ranked at the scoping session against the unified
   competency, not silently displaced by it.
3. **Planning/scheduling ceiling measurement is an M10 design-round
   obligation** before any promotion run (the ADR-0073 standing rule,
   applied forward).
4. **Evalset repair rides with M10's label work:** phyrexian positives
   are value-free at game end (Δ=0.0 exactly) and wide_choice needs
   reachability repair (+7.5pp) — those 27 drills enter no future
   denominator until repaired (ADR-0069/0073 finding, now routed).

## The payment-completion queue, routed by name (the no-silent-loss rule)

1. **Directed-payment executor completion — RESOLVED MOOT**
   (ADR-0065, unchanged).
2. **Cost-composition cousins — SCHEDULED into M10's actuation
   build.** The unified competency re-opens the payment family;
   cheapest completion, wire shape exists. If M10 scoping ranks the
   charter differently, the item returns to the table by name.
3. **Resolution-effect payments — RE-DEFERRED, reason recorded:** a
   different decision genre (pay-or-suffer at resolution) needing its
   own probe-then-build round per the §3c template; not required by
   the unified competency's v1. Named on the M10 scoping table;
   largest deferred traffic slice (~54/g), so it may not be re-deferred
   a second time without a measured argument.
4. **Costmod per-spell refinement — SCHEDULED with item 2** (both
   touch `CostAdjustment`; returns ~25% of in-scope traffic to the
   model).
5. **Pool-tie enumerator residual — SCHEDULED with items 2/4** on the
   next payment-family touch, never mid-era (the gate-session
   decision 3 rationale, unchanged).

**Pin-12 forced-family re-mine — RETIRED as an M9 obligation, reason
recorded:** it was owed as an instrument for run18's read; ADR-0069
closed that read negative without it, run18's stores are veto-elevated
and mixture-banned, and the M4 standing rule regenerates curation from
the current ckpt-of-record's own losses every cycle — M10's actuation
round re-mines from its own era by construction. Nothing consumes a
run18-era forced mine.

**Post-M9 drill candidates carried (named, unranked):** combo-enabler
valuation drill families (perception floor landed in M9's boundary
bundle; valuation via targeted Grindstone families, D2a genre).
**Tier-3 search** stays parked behind the critic-ordering constraint
(ADR-0061's 0.42-vs-0.94, unchanged).

## Standing rules born in M9 (consolidated)

- An evalset's **certification horizon is part of its type** — never
  let "certified" stand unqualified in a strength argument (ADR-0072).
- **Measure the ceiling before building the learner** (ADR-0073).
- A re-cert threshold on a selected population must price
  **winner's-curse regression**, not only drift (ADR-0073).
- **Per-window value and gate-scale value are distinct claims** — a
  ceiling statement carries both (ADR-0073).
- Gate a capability on a **discrimination statistic**, never an
  accuracy count; a day-zero-0-correct sub-population is a gate defect
  (ADR-0069).
- A recipe pin that removes a condition must be **re-checked against
  every pre-registered readout**; read EVERY pre-registered signal; a
  control restores the CONDITION, not the asset (ADR-0069/0072).
- Check whether candidate curation stock is **gate-seeded**
  (ADR-0068).
- An enumerator's **unit of exclusivity** must be the unit the
  executor consumes (ADR-0066).
- Price a conditioning channel's lr by **gradient density**, not init;
  a recipe-change relaunch must clear the rejected phase's artifacts;
  **an aux-target's shape is a behavioral prior**; falling reliance +
  compounding behavior = absorption, read jointly (ADR-0076).

## Assets carried out of M9

- The **payment surface as infrastructure**: legality-derived
  enumeration + float-then-apply executor + `payment_certify.py`
  (2-turn proxy, ADR-0072 retype) + the certified salvage rule.
- The **full D6 plan machinery** (model/serve/loop/tests, 242 suite),
  `plan_reliance.py` + day-zero bank, `d6-plan-init`, the amended
  launch recipe (split lr groups).
- **ADR-0075's label universe**: 5,076 tagged windows, the uniform-600
  sweep, stage-2 conversion arithmetic — the M10 candidate's seed
  stock.
- `veto-knowability-*` instrument dirs (the v2 read across eras) and
  `rankcrit_audit.py`/`critic_select.py` from M8, unchanged.
- The boundary bundle: engine pin `23c3d2a85d`, obs schema v2,
  multi-format, forkcheck 10.0%.

## Stale-data kill list (presented for sign-off at the closeout session)

Per the standing milestone-close habit. Keeps verified: ckpt of record
(`d6-run11`), `d6-plan-init`, drills/selection/evalset assets,
baseline-era arm stores (`m9-rebaselinearm`), Ante ledgers, all
`veto-knowability-*` dirs, `plan-probe-r1`, `payment-evalset-v1`,
ratesweep + ceiling census dirs (ADR-0075/0073 evidence + M10 seed
stock). The kill list itself is recorded in the closeout session's
devlog; run18/19/20 eval stores, trajectory stores, training iter
payloads (trimmed to the run16 shape: keep `analysis/`,
`monitor.jsonl`, `loop_config.json`, `loop_state.json`), and the
m9control drillmix scratch are the deletion candidates.

## Consequences

- M9 is CLOSED. The status bullet moves to the archive; the compact
  summary carries the two verdicts (mechanism FALSIFIED; strength: no
  promotion, superseded done-when with the reason above).
- M10 opens with a scoping/design round, not a build: charter
  adjudication (unified competency vs §3b stops ranking), the
  planning ceiling measurement, the v2 target probe, and the queue
  items scheduled above.
- `d6-run18/19/20` stores remain veto-elevated and mixture-banned
  permanently (the run14/15/16 rule).
