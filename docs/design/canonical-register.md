# The canonical register — philosophically-correct future forms, named and priced

*Born at the M10 build design session (2026-08-26, user direction):
"canonical solutions that might require additional design work or
computing power are still very much worth considering across the
board." Each entry records the STAGED form we build now, the CANONICAL
form it approximates, and the instrument or evidence that would fund
promotion — the deferrals-need-named-routing rule applied to design
ambition. Entries are reviewed at scoping sessions; nothing here is a
commitment, everything here is findable.*

Convention per entry: **Now** (the staged form and why it's enough) /
**Canonical** (the correct endpoint) / **Funds it** (the named
instrument, measurement, or evidence bar).

## 1. Expectation watch-sets (model-placed revision triggers)

- **Now:** four fixed engine-detectable triggers (own veto / opponent
  action / EOT entry / schedule exhausted), pinned at the M10 cadence
  adjudication.
- **Canonical:** the model attaches falsifiable expectations to its
  plan ("this survives," "they hold ≤2 untapped"); the engine grades
  them; violations prompt revision. The purest form of
  engine-adjudicates-every-claim. Note v2 already ships the
  resource-domain version: per-slot affordability bits and the
  end-state claim ARE model-emitted, engine-graded expectations.
- **Funds it:** the missed-revision residual in the birth telemetry —
  deviations/degrades with no preceding trigger. Large residual ⇒ this
  returns with a number; small ⇒ stays shelved.

## 2. Plan-level search at serve (Tier-3, re-founded)

- **Now:** no serve-time search (parked behind the ADR-0061
  critic-leaf constraint); the ceiling sweep's enumerated-arm ×
  K-rollout oracle is exactly this search, run OFFLINE as measurement.
- **Canonical:** lookahead over emitted schedules — the schedule
  object is a native macro-action, collapsing the branching factor
  from per-priority-window actions to per-turn plans; the sweep proved
  the value of the best node is real (+13.5pp/game ceiling) and the
  h2 composite / critic are candidate leaf evaluators.
- **Funds it:** the gap between the trained model's realized gain and
  the measured ceiling (whatever the M10 promotion run leaves on the
  table is search's addressable market), plus ADR-0061's ordering
  constraint being satisfied by a future critic. Compute-priced by
  construction (K rollouts or critic leaves per candidate schedule).

## 3. Belief-state opponent modeling

- **Now:** hidden information is handled implicitly — the policy
  conditions on observable correlates (untapped islands, deck
  archetype, graveyard); the full-vis critic exists but is
  instrument-only, never policy (§7 constraint). The M10 hold-up
  competency is EMERGENT from this.
- **Canonical:** an explicit, downstream-verified belief head over
  hidden zones (opponent hand class / threat posture). The counter-deck
  scenario that motivated the contingent-line rider PRESUPPOSES this:
  "worried about a counterspell but not a board wipe" is a belief
  statement. Note the LLM-judgment invariant analogue: beliefs are
  filtered conditioning, verified against revealed information at game
  end — never trained as truth.
- **Funds it:** hold-up telemetry stratified by actual opponent
  holdings (revealed ex post from full-vis logs): if the model's
  reserved-mana behavior fails to differentiate live threats from dead
  ones where observables sufficed to tell them apart, the emergent
  path is saturating short of the competency.

## 4. Cross-turn and off-turn plan persistence

- **Now:** the plan is turn-keyed, own-turn only (v1 carry semantics;
  cross-turn persistence explicitly out of v1 AND v2).
- **Canonical:** intent spanning turns (setup lines, "hold these two
  until their end step, combo next turn") and off-turn schedules — the
  census measured the off-turn terrain: 37.8% of off-turn groups
  ≥2-affordable, 19.8% resource-bound. Off-turn holding IS scheduling.
- **Funds it:** an off-turn analogue of the M10 ceiling sweep (the
  `-forceschedule` machinery generalizes: fork at opponent-turn
  windows, force hold/act arms). Cross-turn needs the harder case
  first: evidence that turn-local plans plateau while multi-turn
  structure is visible in the errors (drill families that need turn
  t−1 setup).

## 5. Plan-complete slots (targets / modes / X in the schedule)

- **Now:** schedule slots are SA-level pointers + payment assignments;
  targets/X are fitted by the policy at execution (the CastPlan
  legality-derived lesson, 65%→~5% vetoes).
- **Canonical:** a slot specifies the complete action — SA + targets +
  modes + X — making the whole line engine-checkable at emission. The
  sweep measured exactly this gap: divergence is VETO-DOMINATED
  (realizer targets/X fitting is the binding failure surface, 73% of
  degrades), not affordability.
- **Funds it:** the v2 follow/validity telemetry's realization-failure
  class staying dominant after training (if the policy learns to fit
  its own plans' steps, the gap closes emergent; if realization breaks
  persist on followed plans, the slots need the specification). The
  feasibility probe target (sweep rows, 96k forced executions) reads
  whether realization validity is predictable from state at all.

## 6. Combat-inclusive turn plans

- **Now:** the schedule covers casts/activations; combat declarations
  stay with the policy on every arm (they are not priority windows —
  the sweep's own convention), and the D5 combat heads are a separate
  surface.
- **Canonical:** the turn plan carries attack/block intent — "cast
  these, then attack with those" is one plan, and mana held for
  combat tricks couples the two halves through the same resource
  ledger.
- **Funds it:** a combat-arm extension of the schedule sweep genre
  (force attack-set arms alongside cast schedules at the same fork
  points); certification rate on combat-coupled turns vs cast-only
  tells us what the coupling is worth.

## 7. In-graph credit through the plan chain

- **Now:** stop-grad carry across emissions/revisions (v1 mechanics;
  BPTT rejected as GPU-hostile, two-pass-hostile, serve-parity risk).
- **Canonical:** end-to-end credit — downstream outcomes shape the
  plan REPRESENTATION through the graph, not only through the aux
  loss and the conditioning benefit.
- **Funds it:** evidence that plan quality is the binding constraint
  while plan-aux gradients are saturated (aux converged, reliance
  high, strength flat) — the M6 elimination-chain genre applied to
  the plan channel. Priced in loop-architecture work, not just FLOPs.

## 8. Exact payment matching in the schedule scorer

- **Now:** the knob-c scorer picks GoalOptions by a greedy
  least-flexible-unit matcher with census-consistent optimism
  (measured perfect at sweep scale: 25,570 directed, 0 salvage/fail —
  at CURRENT pool complexity).
- **Canonical:** exact feasibility (matching/flow over the turn's full
  payment plan). A bounded, well-understood computation — the cheapest
  entry on this list.
- **Funds it:** any nonzero salvage/fail rate appearing as the pool
  widens or cost-composition cousins (convoke/improvise/delve) land —
  the counters already exist and are watched.
