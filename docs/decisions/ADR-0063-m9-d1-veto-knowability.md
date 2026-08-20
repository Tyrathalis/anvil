# ADR-0063: M9 D1 — veto knowability decomposition: the interface-theory premise STANDS (knowable ≥ 0.50 in all four populations); the collapse baseline is on file

- **Date:** 2026-08-19
- **Status:** accepted
- **Design-doc anchor:** [m9-plan.md](../design/m9-plan.md) D1 (gate and
  method pinned at the 2026-08-19 D1 session, pre-data); ADR-0062 (the
  standing veto account this premise-checks)

## Question

Of the vetoes the current policy eats, what fraction are
knowable-from-public — the acting seat's OWN observation carried enough
information to know the cast was unaffordable/illegal? Pre-registered
gate (pinned before any classification ran): knowable fraction ≥ 0.50
on the first-attempt, mana-relevant basis (`unpayable` + `timing`) ⇒
the interface-theory premise stands and the D4/D5 veto-collapse metric
is defined on the knowable subset.

## Instrument

`scripts/veto_knowability.py` (standing asset; 22 unit tests): joins
census veto records to the raw obs stream at (g, s) — census `s` is
cumulative per worker, obs `s` per game; the join subtracts the game's
census base — and computes affordability from the observation the model
actually saw: untapped battlefield sources through a card table parsed
from the fork's card scripts (34,411 entries: ManaCost, per-permanent
choose-one production with Amount$ multi-mana units, tokens, multiface
back-faces), commander tax via `cmdcast`, cost-modifying statics
(RaiseCost/ReduceCost with coarse Valid/Activator filters;
tax-knowable only when the engine's own unpayable verdict corroborates).
OPTIMISTIC by construction — phyrexian payable via life, X=0,
Combo/Any/ColorIdentity as any color — so `knowable` verdicts are
conservative and every unsettleable window lands in a named `uncertain`
bucket inside the gate denominator. **The pinned fractions are lower
bounds.**

**Validity bar (pinned ≥ 0.95): PASSED in all four populations** —
0.986–0.993 of engine-accepted first-attempt casts called affordable
(the free engine-adjudicated negative control; residual misses are
cost-reduction statics and card-table gaps).

**Data note:** the M8 kill list had removed every current-era
sampled-play census. Restored 2026-08-19 from the kopia pre-kill
snapshot (08-19 08:00, `k4b35ddf`): the `d6-run17-i000*` trio —
generation from run17's *init*, i.e. `iter-019` itself at training
temperature (veto rate 0.195 = ADR-0062's recorded iter-0 baseline) —
plus `m8stock*` (argmax per `cycle_stock.py` `sample=False`) and, on
user direction, the full `d6-run17-i001..i011` iteration dirs (the veto
climb; the only complete-run17 snapshots were 08-19 hourlies expiring
within ~48h). NOT restored, kill rationale standing: run17 training
trajectory stores, drillmix-m8stock campaign dirs + fork trajectories.

## Result — gate PASS, all four populations

First-attempt, mana-relevant basis; Wilson 95% CIs:

| population | policy / serve | n | knowable | CI95 | first-veto rate | knowable-veto rate |
| --- | --- | --- | --- | --- | --- | --- |
| sampled | iter-019, training temp | 2,476 | **0.5347** | [0.515, 0.554] | 0.1562 | **0.0583** |
| argmax | iter-019, rebaseline arms | 6,025 | **0.5029** | [0.490, 0.516] | 0.1162 | **0.0429** |
| argmax_stock | iter-019, m8stock | 18,057 | **0.5282** | [0.521, 0.536] | 0.1391 | 0.0466 |
| elevated | run17 i009/i010 argmax | 27,421 | **0.5993** | [0.594, 0.605] | 0.1428 | 0.0680 |

**Premise verdict: STANDS.** The primary populations (sampled, argmax)
clear the 0.50 pin — argmax at the line (CI straddles), sampled and
stock clean, and these are lower bounds under the instrument's
conservative construction. **The D4/D5 knowable-veto collapse baseline
is the knowable-veto rate column: 0.0583 sampled / 0.0429 argmax**
(knowable first-attempt mana-relevant vetoes per first-attempt window).

## Taxonomy findings (shape the D3 class design)

1. **generic_short dominates knowable mass** (sampled 36% of classified,
   elevated 48.8%) — raw quantity probing, not color arithmetic;
   colors_short is second (10–16%); statics_tax (Thalia-family taxes,
   engine-corroborated) and timing are real but small.
2. **The veto climb happened in the knowable channel.** The elevated
   population (run17's tied candidates) is MORE knowable than baseline
   — 0.5993 vs 0.5029 argmax, generic_short swelling from 31% to 49% —
   run17's training-elevated vetoes are dominantly knowable-affordability
   probes. ADR-0062's "elevation is exploration-side probing" account,
   now measured at the taxonomy level.
3. **The not_knowable mass is mostly auto-payer artifact, not hidden
   info.** Unpayability has no hidden causes (costs depend only on
   public state + own hand). The largest bucket, `obs_says_payable`
   (15–17%), is the AI cost machinery (`ComputerUtilCost.canPayCost`,
   the exact `unpayable` emission site in `CastPlanRealizer`) refusing
   arithmetically payable boards — consistently (4/1005 same-window
   rescue rate), flash-card-skewed. Named refusal families measured
   directly: `autopayer_xcost` (X spells the payer won't size),
   `autopayer_phyrexian` (life payments it won't make),
   `payable_needs_creatures` + `tap_ability_sickness` (summoning
   sickness — public at the table, ABSENT from the obs schema: a
   representation gap for D2a/D3), `interface_mana_ability`. These are
   ADR-0062's blind-spot families, live in baseline data — D3's engine
   capability audit targets exactly this code path.
4. **Uncertain mass (26–30%)** is dominated by chained-source-available
   (the chained-activation class D3 must expose), dec_missing (torn
   obs tails), multiface modes, and alt-costs — all named, none silent.

## Consequences

- D4/D5's mechanism check reads knowable-veto rate against 0.0583
  (sampled) / 0.0429 (argmax), per population, first-attempt basis.
  Falsification stays first-class: a payment head that trains without
  collapsing the knowable rate falsifies the interface theory.
- D2a proceeds (bench design next): affordability labels are free from
  this instrument's joined windows; probe on `[STATE]` per the M6 rule.
- D3 class design inherits the taxonomy: generic quantity first, colors
  second, chained-activation exposure mandatory (uncertain mass),
  sickness representation flagged for the obs schema decision.
- Standing-asset candidate confirmed: the classifier doubles as
  run-battery telemetry (knowable-rate per iteration) once D4 runs.
- Restored run17 iteration dirs (2.1G) are M9-era forensics; re-priced
  at the M9 close stale-data pass.

## The climb rider (descriptive, not gated)

Knowability along run17's sampled veto climb (restored iteration dirs;
first-attempt basis; full tables in
`data/runs/veto-knowability-m9d1-climb/report.json`):

| iter | first-veto rate | knowable fraction | knowable-veto rate |
| --- | --- | --- | --- |
| i000 | 0.1562 | 0.5347 | 0.0583 |
| i003 | 0.1586 | 0.5222 | 0.0556 |
| i006 | 0.1431 | 0.5218 | 0.0527 |
| i009 | 0.1683 | 0.5223 | 0.0573 |
| i011 (halt) | **0.2461** | **0.5857** | **0.1042** |

Flat through i009, then the guard-halt iteration near-doubles the
knowable-veto rate — ≥60% of the terminal runaway increment is
knowable-classified (a lower bound under the instrument's
conservatism). The veto guard has been halting on knowable-affordability
probing: the D5 comparison curve now has both a baseline level AND the
runaway signature the payment head is predicted to remove. Validity bar
held 0.973–0.988 across all climb checkpoints.

## Addendum (2026-08-19, same day): instrument v2 — the sickness claim was
## backwards; baseline RE-PINNED (gate verdict unchanged, slightly stronger)

**The correction.** Finding 3's claim "summoning sickness — public at the
table, ABSENT from the obs schema" is **wrong**: `ObsSnapshot.java` emits
`sick:1` from the engine's `isSick()` for battlefield creatures
(observation-schema-v1 line 62), and the transform feeds it as entity
feature #5. The v1 instrument was written on the absent-belief and
*guessed* sickness wherever it could explain a veto. User-prompted
spot-checks against the raw observations showed the guesses were wrong in
both directions:

- `tap_ability_sickness` (261 windows): 12/12 spot-checked hosts entered
  the battlefield turns before the veto, `sick=0` — never sickness;
  228/261 were `no_shape_fit` (outside the gate) and the rest are
  auto-payer/realizer artifacts.
- `payable_needs_creatures` (468 gate-relevant windows): the needed
  creature sources WERE flagged `sick=1` in the majority (8/14 spot-check,
  ~52% at scale) — genuinely unaffordable AND visible in the model's own
  input: these belong in `knowable`. ~25% turned out payable only through
  spend-restricted / board-cost production (Delighted Halfling
  `RestrictValid$`, Urza `tapXType` — a previously unmodeled family),
  ~13% pure `obs_says_payable` artifact.

**Instrument v2 (sick-aware; 32 unit tests, suite 198 green):** production
units carry `needs_tap`/`conditional`/`zone`; affordability is computed
over three nested views (usable-now ⊆ +conditional ⊆ +sick) yielding new
verdicts `knowable/sickness_short`, `knowable/ability_sick`,
`uncertain/conditional_production`; the two guessing branches are retired;
`ActivationZone$ Hand` mana (Simian Spirit Guide) now counts from hand and
never from battlefield; tapped hosts keep non-tap-cost abilities; a
first-pass regression (tapped/sick variable sources blocking knowable
verdicts) was caught by the v1→v2 window diff and fixed —
variable-amount downgrades now require an activatable source.

**Re-pinned result (v2; first-attempt, mana-relevant; Wilson 95% CIs):**

| population | n | knowable (v1→v2) | CI95 v2 | knowable-veto rate (v1→v2) |
| --- | --- | --- | --- | --- |
| sampled | 2,476 | 0.5347 → **0.5392** | [0.520, 0.559] | 0.0583 → **0.0588** |
| argmax | 6,025 | 0.5029 → **0.5097** | [0.497, 0.522] | 0.0429 → **0.0435** |
| argmax_stock | 18,057 | 0.5282 → **0.5336** | [0.526, 0.541] | 0.0466 → **0.0470** |
| elevated | 27,421 | 0.5993 → **0.6044** | [0.599, 0.610] | 0.0680 → **0.0686** |

Gate PASS everywhere, fractions up ~0.5pp: correcting the guess moved mass
INTO knowable, as the conservative-lower-bound construction promised.
**The D4/D5 collapse baseline is superseded: 0.0588 sampled / 0.0435
argmax.** Validity bar improved or held in every population (main
0.986–0.991; climb 0.9846–0.9897 vs v1's 0.9731 low). Climb rider v2:
kvr 0.0588 → 0.0561 → 0.0535 → 0.0578 → **0.1049** at the i011 halt —
the flat-then-double signature is unchanged.

**Consequences, amended:**

- Finding 3's "sickness absent from the obs schema: a representation gap
  for D2a/D3" is WITHDRAWN — sickness is present in the input and D3's
  class design may use it as-is. The not_knowable mass is now purely
  auto-payer willingness/interface families (obs_says_payable, X,
  phyrexian, mana-ability routing).
- New named uncertain family `conditional_production` (~1–2% of gate
  mass): spend-restricted (`RestrictValid$`, 186 pool-folder cards) and
  board-cost (`tapXType`) production — a real enumeration input for D3
  (restricted mana is a payment-class residual distinction).
- v1 outputs retained at `data/runs/veto-knowability-m9d1{,-climb}-v1`
  (43M, regenerable: v1 script in git + stores kept) — re-price at the
  M9 close stale-data pass.
