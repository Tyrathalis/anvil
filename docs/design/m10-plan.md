# M10 plan — the unified resource-scheduling competency (SCOPING DRAFT)

*Status: SCOPING (opened 2026-08-25 at the M9 closeout,
[ADR-0077](../decisions/ADR-0077-m9-closeout.md)). This is the
skeleton the design round fills in; every fork below is user-adjudicated
before anything builds. Nothing in this file is a pin yet except the
inherited obligations, which carry their own ADR authority.*

## Charter (candidate, to be adjudicated)

**Turn planning and payment handling are ONE competency — within-turn
resource scheduling — split across two surfaces by our architecture**
(user framing, [m9-d6-plan-latent-spec.md](m9-d6-plan-latent-spec.md)
ledger, 2026-08-25). The human prior: most turn planning is sequencing
to fully use the turn's resources (a mana rock effectively costs 1
cast-before-use, 2 otherwise; holding up interaction mana;
activation-cost lands). The project's evidence converges on it:
ADR-0065's Signet-chain board, the auto-payer-blank card class, run20
i1's 288 `chained_source_available` veto windows, the
color_hold/blocker drill shapes.

Candidate shape (the three legs, trained and READ as one competency):

1. **v2 schedule-bearing plan target** (M9 D6's validated mechanism,
   new target): ordered/arrival-indexed actions + a resource-schedule
   component (end-of-turn untapped/floating, or
   affordability-at-execution — pulling D2a's measured cost knowledge,
   AUC 0.881, INTO the conditioning channel).
2. **Re-advertised payment actuation** (capabilities-over-fallback):
   the M9 payment surface graduates from infrastructure to an
   advertised action capability.
3. **ADR-0075 supervised conditional labels**: the 5,076-window tagged
   universe + certify machinery as the dense conditional signal —
   the path the ceiling arithmetic funds (≈+2.96pp/game, ~2.7× the
   gate floor) and the one the marginal path measurably is not.

Corollary carried from the framing: each capability surface reveals its
own training-data requirements — rare-decision competencies need
targeted data, and which data only becomes visible after the surface
opens.

**The substrate corollary (user, 2026-08-25 scoping discussion): the
plan latent is plausibly the prerequisite for any downstream capability
expansion to show its full potential.** A tutor-target head without a
plan representation falls back on marginal card-quality ranking; a
schedule-bearing plan latent is the natural conditioner for
intent-driven tutoring (and for stops, modal choice, library ordering —
the §3d′ families generally). This is the sequencing argument for
keeping the unified competency as M10's headline while the coverage
families queue behind measured ceilings: plan-first is not deferring
those competencies, it is building their substrate.

## Named scoping alternatives (ranked at the design round, not silently displaced)

- **§3b learnable stops** — the M8/M9 carry; biggest deferred
  episode-shrinkage lever (`autoPassCancel` top-5 traffic);
  philosophically part of the interface family. Working read going
  into the round (to be adjudicated, not assumed): an
  episode-economics lever more than a strength lever, so it ranks
  behind the charter — the design round records that ranking
  explicitly.
- **Mid-resolution object choices (§3d′ family 2) — NAMED at the
  2026-08-25 scoping discussion (user-raised): tutor and fetch
  targets, discard/sac picks** (`chooseSingleEntityForEffect`,
  `chooseCardsForEffect`, …). The ledger's own rank: largest excluded
  class by game impact in a tutor-defined format — the model casts,
  the heuristic resolves. Answer shape is cheap (the pointer decoder's
  native operation), but its ceiling is UNMEASURED and its raw signal
  structure (rare windows × ~90-card branching) is the
  marginal-vs-conditional collapse shape that killed the payment head
  twice — the supervised-conditional machinery it would need does not
  exist yet. Disposition agreed: not M10's build; gets the funded
  ceiling probe below, and returns to the M11 table with a number.
  Interaction recorded: intent-driven tutoring conditions on the plan
  latent (the substrate corollary above), so the charter builds toward
  it.
- Anything else the design round surfaces from the anvil-design-v2
  §3d′ coverage ledger.

## Design-round obligations (before any build — inherited pins)

1. **Planning/scheduling ceiling measurement** (the ADR-0073 standing
   rule: measure the ceiling before building the learner). The payment
   leg's ceiling is measured; the planning leg's is not.
2. **v2 offline target probe** (the ADR-0074 pattern) — run INSIDE the
   design round so the target is co-designed with the actuation
   surface, not pinned before it (the ADR-0077 sequencing decision).
3. **Escape argument + pre-registered kill signal** for whatever
   conditioning channel ships (the D6 design-session discipline —
   carried; run20 proved the kill wiring earns its keep).
4. **Evalset repair before those 27 drills enter any denominator**:
   phyrexian value-free at game end (Δ=0.0), wide_choice reachability
   (+7.5pp) — rides with the label work (ADR-0069/0073, routed at
   ADR-0077).
5. **Aux-target shape review**: an aux-target's shape is a behavioral
   prior (ADR-0076) — the v2 target's shape gets the same adversarial
   read v1 should have had.
6. **Two named ceiling probes, funded at the 2026-08-25 scoping
   discussion (user-agreed) — session-scale measurements riding the
   design round, routing M11, not gating M10's build:**
   - **Tutor/fetch-target ceiling** (§3d′ family 2): on mined
     tutor/fetch windows, fork the state, force each of the top-k
     candidate targets, roll out, read heuristic-vs-best delta — the
     ADR-0073 genre on the ADR-0053 forced-branch machinery. Both
     claims per the standing rule: per-window value AND gate-scale
     value (traffic-weighted).
   - **Resolution-effect payments ceiling** (`payManaCost`
     `effect=true`, ~54/g): same genre on pay-or-suffer windows. This
     IS the measured argument ADR-0077 requires before the item can be
     re-deferred a second time — the probe result either schedules it
     or re-defers it with the number attached.

## Scheduled in from the payment-completion queue (ADR-0077 routing)

- **Cost-composition cousins** (convoke/improvise/delve/
  `payCombatCost`) — with the actuation build; cheapest completion,
  wire shape exists.
- **Costmod per-spell refinement** — pairs with the cousins (both
  touch `CostAdjustment`); returns ~25% of in-scope traffic.
- **Pool-tie enumerator residual** (`min_life` lex-hidden plan) —
  lands on the same payment-family touch, never mid-era.
- **Resolution-effect payments** — RE-DEFERRED at ADR-0077 (own
  probe-then-build genre); on this table by name, and per the
  closeout it does not get re-deferred again without a measured
  argument. **That argument is now funded: design-round obligation 6's
  effect-payment ceiling probe supplies the number either way.**

## Open forks for the design round (none adjudicated)

- Charter ranking: unified competency vs §3b stops vs sequenced both.
- v2 resource-schedule component: end-of-turn untapped/floating vs
  affordability-at-execution (or both, probed head-to-head à la
  ADR-0074).
- Actuation advertisement shape: how the payment capability surfaces
  in the action schema (re-advertised tag per
  capabilities-over-fallback).
- Read protocol: what "read as one competency" means for the gate —
  the standing 2,000-game paired read is the strength instrument;
  what is the competency instrument, and what certification horizon
  does it carry (the type rule)? Candidate instrument shape from
  community prior art (LordOfThePigs, Discord 2026-08-25): mean
  per-decision gain BINNED BY pre-decision state score — his draft
  version showed the skill gap exists only in the middle-difficulty
  band (bad states improve under any agent, saturated states under
  none), which is the same locus-of-signal structure as ADR-0024's
  near-tie argument and M9's certifiable windows. A binned-gain curve
  over payment/plan windows would make "where the competency lives"
  a readable curve instead of a single number.
- Supervised-conditional wiring: label ingestion path (Grindstone
  family vs direct aux) and its era-scoping.

## Explicitly out (inherited, unchanged)

- Tier-3 search (parked behind the ADR-0061 critic-ordering
  constraint).
- Deterrence-family anything (closed at ADR-0062).
- Combo-enabler valuation (post-M9 drill candidate; perception floor
  landed, valuation via targeted drill families later).

## Done-when (drafted; the design round finalizes)

1. Design round closed with an ADR: charter adjudicated, forks pinned,
   ceilings measured (planning leg + the two obligation-6 probes:
   tutor targets, effect payments), v2 target probed, kill signal
   pre-registered.
2. The build lands with telemetry from birth and the probe-first
   discipline (D4-shape short run before any promotion run).
3. One promotion-scale run closed by the standing 2,000-game combined
   paired read vs the 0.5279 ± 0.0110 baseline — or closed early by
   its pre-registered kill signal with an ADR.
4. The competency read (instrument pinned at the design round)
   resolves alongside the strength read — both claims, per the
   per-window/gate-scale rule.
5. The closeout ADR routes the remaining queue items by name
   (no-silent-loss, as always).
