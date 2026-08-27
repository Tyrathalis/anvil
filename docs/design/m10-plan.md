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

## Planning-ceiling measurement — fork map (2026-08-25 design session)

*→ The pre-registration spec is **ADJUDICATED** (user, 2026-08-25):
[m10-ceiling-spec.md](m10-ceiling-spec.md) — two-stage h2-certify →
game-end conversion + h4 side-sample, all five knobs accepted.
Remaining pre-launch: `-forceschedule` build + smoke; θ / h4-threshold /
seed-base / rng pinned at the launch commit pre-data.*

*The obligation-1 instrument. Fork list laid out and discussed with the
user 2026-08-25; leanings recorded below are user positions, pinned
formally at the pre-registration commit before any rollout runs.*

1. **Oracle definition:** enumerated/sampled turn-script arms
   (empirical oracle, primary) + best-of-K policy resample (reachable
   ceiling, secondary) — the (a)−(b) gap routes the data question
   (large gap ⇒ right lines absent from the policy distribution ⇒
   targeted drill families).
2. **Schedule scope — USER LEANING (2026-08-25): directed payment is
   IN the schedule** (the competency is joint, measure it jointly);
   the auto-pay marginal stratum is RETAINED alongside — it supplies
   the attribution split vs the measured +2.96pp payment leg and the
   first super-additivity read on the compounding-surface hypothesis.
3. **Population/rate:** uniform turn-group sampling (the ADR-0075
   lesson at birth, never mined-only); ≤1-candidate-schedule turns
   excluded from arms but counted in the rate denominator; mined
   stratum exploratory only, winner's-curse-priced. Store: fresh
   small generation from `d6-run11/iter-019` at the boundary bundle
   preferred over veto-elevated run-18-era mirrors.
4. **Horizon:** game-end conversion primary; the N-turn board/tempo
   proxy read free off the same truncated trajectories
   (`payment_ceiling.py` genre) — calibrates any future scheduling
   certify proxy. Certification horizon typed at birth.
5. **Divergence policy (forced-script arms), two layers kept
   distinct:** (i) MEASUREMENT arms — degrade-to-auto-and-count with
   a pre-registered void cap per arm (exhaustion precedent,
   ADR-0053); divergence RATE is itself a free instrument
   (schedule×payment entanglement). (ii) MODEL semantics — USER
   DIRECTION (2026-08-25): long-run serve behavior is halt-at-veto
   and REPLAN from the veto point; whether replan-at-veto or
   push-through-degrade trains better in early eras is an OPEN fork
   for the v2 actuation design, explicitly not settled by the
   measurement's arm policy.
6. **Invalid-schedule penalty — USER DIRECTION (2026-08-25): yes,
   small, the §6c-veto-penalty rationale.** Design constraints from
   standing evidence: KNOWABILITY-GATED (penalize knowably-invalid
   schedule steps only — the deterrence-closed account, ADR-0062,
   says punishing unknowable invalidity punishes rational probing;
   the veto-knowability instrument v2 is the splitter) and
   CALIBRATED under the ADR-0053 rule (a penalty never exceeds the
   measured cost of the behavior it deters). Presupposes an explicit
   schedule decode on the actuation surface — feeds the v2 target /
   actuation co-design, adversarial shape review applies.
7. **Budget — USER DIRECTION (2026-08-25): overbudget deliberately.**
   No expectation that plans are compute-efficient during training;
   early-cancel is for a clear null plus suspected implementation
   error, not for cost. Quiet-box rule for the calibrated read.
8. **Read:** pre-registered primary (paired best-vs-natural Δwr,
   clustered by game, uniform population), gate-scale formula carrying
   both claims, health guards priced for winner's curse on any
   selected stratum, funding thresholds vs the payment leg pinned
   pre-data. Binned-gain curve (the LordOfThePigs instrument) emitted
   as the exploratory competency-instrument prototype.
9. **Co-design dividend:** the arm representation (ordered actions +
   hold-set + payment assignment + resource outcome) IS the v2
   target's vocabulary; best-arm schedules become seed supervision
   (the ceiling-drills.jsonl precedent).

**Pre-instrument census — RUN 2026-08-25** (`scripts/schedule_census.py`
→ `data/runs/schedule-census-m10/`; population `m9-rebaselinearm` s0+s1,
1,999 games, model seat, post-boundary era, cost/affordability
conventions shared with the veto-knowability v2 instrument). Headline
terrain, own-turn stratum (22,241 turn-groups, 11.1/game):

- **63.7% of own turns have ≥2 individually-affordable schedulable
  actions** (~7.1 turns/game); 27.2% sit in the §15-bet 3–4-action
  regime (~3.0/game); ~19% have ≥5 (enumeration-infeasible tail).
- **31.6% of own turns are RESOURCE-BOUND** (affordable demand exceeds
  mana capacity — the model cannot cast everything it can afford,
  ~3.5 turns/game; half of all ≥2-affordable turns). Scheduling has
  real terrain at 10–30× the payment window rate (0.11–0.32/g) — the
  frequency-structure argument now carries a measured base.
- **17.3% of own turns have an untapped chained (Signet-class) source**
  — the ordering-sensitive board is common, supporting the joint
  schedule×payment arm design (fork 2 user leaning).
- Off-turn stratum (11.1 groups/game): 37.8% ≥2-affordable, 19.8%
  resource-bound — the hold-up-interaction terrain is material too.
- Instrument health: 18.5% of turns carry ≥1 cost-unresolvable
  candidate (altcost/multiface/unparsed — arms must handle these
  conservatively); mean realized casts 1.75/turn vs the larger
  affordable set (the model already leaves resources unused).
- **Arm-cap consequence:** ordered-subset space is 5/16/65 at n=2/3/4
  and explodes ≥326 at n≥5 ⇒ full enumeration for n≤3 (52% of
  ≥2-affordable turns), canonical-heuristic + sampled arms under a
  ~16-arm cap above that. Winner's-curse note for the read: best-arm
  selection at K rolls must split selection from scoring (select on
  half the rolls, score on the other half) or the ceiling inflates.

## v2 actuation surface — latent vs emitted schedule (ADJUDICATED 2026-08-25: SOFT EMISSION)

The three-way fork, discussed and decided at the 2026-08-25 design
session (user adjudication):

1. **Pure latent** (v1 shape, better target) — schedule exists only as
   aux supervision. REJECTED as v2's shape: the invalid-schedule
   penalty, replan semantics, Mentor narration, and direct supervision
   on schedule-valued labels (ceiling best-arms, ADR-0075 universe) all
   need the schedule to exist as an object; a latent's plan is
   unfalsifiable, against the engine-adjudicates-every-claim invariant.
2. **SOFT EMISSION — ADOPTED.** The schedule is decoded as a
   first-class engine-checkable object (ordered actions + payment
   assignments) and consumed through the VALIDATED conditioning
   channel; the per-window policy keeps authority and can deviate.
   Deviation/follow/invalid-step rates become first-class telemetry
   (the ADR-0069 discrimination-statistic family) and the fund/kill
   signals get direct behavioral readouts.
3. **Hard execution** (schedule executor, halt-at-veto + replan) —
   NOT rejected, STAGED: a serve-time mode unlocked later by measured
   follow/validity rates, never a training-time bet.

**The user's adjudicating argument (recorded): interaction
robustness.** Instant-speed interaction is common in high-level play;
a hard-executed plan that is abandoned and regenerated the moment an
opponent interacts makes counterspell handling a kludge. The elegant
shape is a plan that is a viewable, MODIFIABLE object at each step —
where the model can implicitly or explicitly hold up mana for its own
interaction and mitigations — and whose value does not depend on the
board progressing exactly as predicted. All plausibly buildable
latent-only, but EMISSION makes it assessable (the second recorded
reason: we can measure follow/deviation/validity only on an explicit
object).

Sub-forks opened under soft emission (pinned at the build's design
sessions):

- **Schedule vocabulary:** pointer-over-candidates + payment-assignment
  slots (strong lean — the CastPlan lesson: legality-derived
  enumeration took cast vetoes 65%→~5%; pointer decoding makes invalid
  schedules mis-scheduled resources, never nonsense, and makes the
  knowability gate computable at emission via source_views/can_pay).
- **Re-emission cadence — ADJUDICATED (user, 2026-08-26): REVISE-ON-
  TRIGGER.** Emit at the first own window; revise ONLY at
  engine-detectable triggers: (1) own scheduled action vetoed/failed
  (fork-5's halt-at-veto/replan semantics falling out of the cadence),
  (2) opponent action resolved during our turn, (3) entry to the
  end-of-turn region, (4) schedule exhausted. Unprovoked revision
  structurally disallowed — plan stability between triggers is what
  keeps follow/deviation telemetry falsifiable (revise-at-every-window
  makes follow≈1 vacuous, the probing shape a third time; once-per-turn
  goes plan-blind after interaction and systematically mislabels
  hold-then-dump). Conditioning across revisions: stop-grad carry on
  (state, prev plan vec) — the v1 carry mechanics at more points, no
  BPTT, two-pass-friendly. **No-op revisions are first-class telemetry**
  ("trigger fired, plan confirmed unchanged" ≠ "plan changed") so
  false-trigger rate stays readable. Wall-clock priced at the smoke
  rung (serve = head pass on the trunk forward that already runs;
  training = pass-0 emission rows ×~2–3), fallback = reduced trigger
  list (veto + EOT) if the price surprises. Open sub-pins for the build
  session: trigger-2 granularity (any opponent action vs
  targeting-us), trigger-3 window (second main vs end step —
  hold-then-dump wants the latest safe window). **Model-placed triggers
  (expectation watch-sets) SET ASIDE (user, 2026-08-26) as the
  canonical future form**: the fixed list's telemetry measures its own
  residual — the missed-revision rate (deviations/degrades with no
  preceding trigger) is the named funding instrument; see the
  [canonical register](canonical-register.md).
- **Conditioning ingestion — ADJUDICATED (user, 2026-08-26): SCHEDULE
  TOKENS + the [PLAN] summary readout kept.** Each slot = a trunk
  token (shared entity/SA embedding + position + afford bit +
  payment-assignment summary + execution status done/next/pending/
  failed); pooled summary still written to the static [PLAN] readout
  (R1 continuity, +0.016 AUC free finding). The three deciding
  arguments: (1) pointer grounding — slot tokens carry entity row
  references, attention connects plan to board natively (the CastPlan
  lesson applied to ingestion; the compressed-vec path pools away the
  entity bindings the sweep says the value lives in); (2) execution
  status is serve-carry bookkeeping between revisions — conditioning
  stays current all turn with zero recompute and without touching
  revision semantics, and a vetoed slot arrives MARKED at the replan
  decode; (3) **the carry becomes discrete** — slot ids + statuses +
  rev index serialize exactly into the labels row, so loader-side
  reconstruction is bit-exact by construction and the v1 tripwire's
  float-drift class is eliminated rather than monitored. ADR-0076's
  validation transfers at mechanism level (the conditioning channel is
  consumed; tokens are a strict superset of the vec). Sub-pins for the
  build session: slot cap (certified-length hist tops at 4; lean 6 +
  mask), slot-embedding payment detail (rides with the actuation-shape
  fork), failed-slot persistence semantics.
- **Validity predicate:** note that "affordability-at-execution per
  intended action" — one of the two v2 resource-component candidates —
  IS the validity predicate; that aux-component fork and this one are
  plausibly the same decision. *(Resolved with the resource-component
  adjudication below, 2026-08-26: affordability is the predicate's
  resource half; the realization half — targets/X fitting, the
  measured dominant degrade cause — rides the feasibility probe
  target.)*
- **Shape-review axis (obligation 5, sharpened):** a validity-rewarded
  schedule head may learn trivially-valid SHORT schedules (the
  scheduling analogue of probing). "Schedule ambition" telemetry
  (scheduled resource utilization vs realized) instruments this from
  birth.

## Open forks for the design round (none adjudicated)

- Charter ranking: unified competency vs §3b stops vs sequenced both.
- v2 resource-schedule component — **ADJUDICATED (user, 2026-08-26
  build design session): BOTH, joint multi-task, the R1 selection
  discipline.** Per-slot affordability-at-execution (the
  sequencing/ledger half; doubles as the validity predicate and the
  invalid-schedule penalty's knowability gate) + end-of-turn
  untapped/floating summary (the selection/hold half — the sweep's 43%
  partial subsets and 11 certified pure holds live here). Probed
  head-to-head offline pre-build (ADR-0074 pattern, gates pinned at
  probe launch), with a THIRD probe target from the sweep dividend:
  **schedule feasibility/degrade-point prediction from state** (96k
  forced executions with real outcomes — the realization-validity
  surface the veto-dominated divergence read names as the actual
  binding failure mode). "No resource component" considered and
  rejected (abandons the unified premise; the census terrain is
  resource-bound scheduling).
  - **Contingent-line rider (user example, 2026-08-26: hold counter
    mana through own big spell, dump into a rock at EOT if unspent):
    conditional schedules stay EMERGENT, not vocabulary.** The
    decomposition is ordering (rock last) + hold-set (counter
    unscheduled, instant-speed off-schedule) + per-window policy
    authority (deviation) + revision; an explicit branching plan
    language is rejected for v2 (unfalsifiable unfired branches). Three
    first-class fingerprints recorded: (i) the deviation-telemetry
    taxonomy must class off-schedule instant-speed action at response
    windows as reserved-mana exercise, NEVER plan break — else training
    pressure kills the flexibility; (ii) the end-state claim is graded
    against the LATEST plan revision — this fork is thereby COUPLED to
    the cadence fork (a second argument for revise-on-priority:
    once-per-turn grading systematically mislabels hold-then-dump);
    (iii) hold-set-preserving affordability ("affordable while keeping
    the hold-set affordable") = v2+ refinement candidate, named not
    built — the emergent path gets its chance first, fingerprint (i)'s
    telemetry reads whether it emerges.
- Actuation advertisement shape: how the payment capability surfaces
  in the action schema (re-advertised tag per
  capabilities-over-fallback) — now partially constrained by the
  soft-emission adjudication above: payment assignments ride the
  emitted schedule's slots; the per-window advertisement is the
  residual question.
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
