# The canonical register — philosophically-correct future forms, named and priced

**Doc status:** living · staged-vs-canonical forms, each priced with its promotion instrument; reviewed at scoping sessions

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

*Reviewed 2026-09-23 at the M12 documentation pass. The M10 planner route
these entries were written against closed NEGATIVE ([ADR-0096](../decisions/ADR-0096-m10-closeout.md));
M12 re-founded the project on search as the behavior policy
([ADR-0101](../decisions/ADR-0101-architecture-review-m12-recharter.md), design
[§3e](anvil-design-v2.md)). Each entry carries a **M12** line: what the
staged form is now, and whether the canonical endpoint moved. No entry is
promoted or dropped here; the next scoping session is the big run's closeout.*

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
- **M12:** no schedule, so no revision triggers; the search re-evaluates at
  every quiescent window it is allocated (the allocation head decides where).
  The canonical form stands unchanged; the funding instrument would now be
  the allocation head's misses — windows it skipped where a search would have
  acted (the floor's labels measure exactly this, recall ≈ 0.86).

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
- **M12: BUILT, in its option-level form.** The search runs at generation
  (the behavior policy, not serve): one ply of options + the surface round +
  the gated deep slot, the value head the leaf (design §3e). The
  schedule-level macro-action is not the unit — options are — and the
  read that would fund plan-level search is the shakedown's deep arm
  (an h2 leaf costs 10× a next leaf; ADR-0106). Serve-time search stays out
  (mobile plays the network alone); the canonical endpoint is now "a
  deeper or wider search shape that buys network-alone gain per box-hour",
  fork L's allocation head generalized to "which shape".

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
- **M12:** unchanged, and now with a second consumer — the search copies are
  determinized to the acting seat's information set by UNIFORM resampling of
  hidden zones (fork J, ADR-0102); a belief head would make that sampler
  belief-weighted. Routed by name at the M12 closeout ("belief-sampled next").

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
- **M12:** the search covers only the acting seat's own quiescent main-phase
  windows (the copier's fidelity boundary — a copy at an opponent-turn or
  in-response window has no faithful fork point, ADR-0117's `never_fired`
  class). Off-turn decisions get no lookahead and no search labels for the
  big run's whole envelope; the instrument that would fund this is a
  fork point at opponent-turn priority once the copier carries the stack.

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
- **M12: LARGELY BUILT as surfaces.** Targets, modes, entity picks, ordering,
  damage and tuck are model-answered callbacks (Build 3–4), and the search
  acts the (option, answer) PAIR (ADR-0106): the complete action is what the
  leaf judges. What remains of the canonical gap is the void class — a
  candidate the decoder cannot plan is never valued (≈ 29% by count, ≈ 3% by
  playability; ADR-0114) — funded by the loop's PG on the decoder's own casts,
  read as the `vr` census each cycle.

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
- **M12:** the search's leaf (the next quiescent window) stops before combat,
  so combat is valued only through the next turn's leaf and the damage
  surface has zero search rows by construction (imitation only, ADR-0105
  evening 3). "Search from combat windows" is routed by name (ADR-0108);
  the end-of-turn leaf family exists (`-searchleaf eot`) and is the cheap
  first read.

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
- **M12:** the plan chain is gone; credit reaches the policy through the
  V-trace PG on every window plus the pick-distillation CE on search-acted
  windows (ADR-0113), and reaches the VALUE head through outcome targets
  alone — which ADR-0118 found pulls it off rollout truth. The canonical
  question re-forms as "what anchors the leaf": the settings pass's value
  anchor is the staged answer; end-to-end credit through the search's own
  leaf values (the leaf as a differentiable target) is the endpoint.

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
- **M12:** the schedule scorer is gone; payment is a SURFACE (the pay slot's
  own expansion under the end-of-turn leaf, ADR-0105 evening 4) and its head
  is withheld — five served heads read negative within one SE of the leaf's
  own prediction. Exact matching is not the gap; the gap is a target the head
  can learn (the h2 pool + the deviation gate are the loop's warm start).
  The ADR-0102 rescue class (`-payrescue`) fires 0.09/game and stays flag-gated.
