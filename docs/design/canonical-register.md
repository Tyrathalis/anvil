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

*Reviewed 2026-11-16 at the M12 closeout documentation pass. The M10
planner route entries 1–8 were written against closed negative
([ADR-0096](../decisions/ADR-0096-m10-closeout.md)). M12 re-founded the
project on search as the behavior policy
([ADR-0101](../decisions/ADR-0101-architecture-review-m12-recharter.md), design
[§3e](anvil-design-v2.md)) and closed positive on scale and open on
mechanism ([ADR-0126](../decisions/ADR-0126-m12-closeout.md)): the network
gained +9.46 ± 0.77pp, and whether search teaches is not attributed. Each
of entries 1–8 carries a **M12** line: what the staged form is now, and
whether the canonical endpoint moved. Entries 9–11 were named during M12.
No entry is promoted or dropped here; the next review is the M13 scoping
session, which reads ADR-0126's routing table.*

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
- **M12: built in its option-level form; deeper and wider shapes read as
  noise; the open question is how the search's result is used.** The
  search runs at generation, not at serve: one ply of options and the
  surface round, the value head as the leaf, the allocation head choosing
  the windows (design §3e). Options are the unit, not schedules. The reads
  that would have funded a deeper or wider shape are in: the shakedown's
  deep arm read +0.55pp over day-zero, doubling the rollouts −1.23 ± 0.83pp, and a
  better-ranking leaf +0.82 ± 1.20pp with lookahead
  ([ADR-0125](../decisions/ADR-0125-value-head-track.md), context). As a
  player the search adds 3.2pp at `big-run/iter-405`. As a teacher it is
  unattributed: it acts on 0.4% of bridged windows, and about 92% of the
  option values it computes reach only the allocation head.
  **The canonical endpoint is now one of two forms, and three arms decide
  between them** (ADR-0126, M13 candidates): a soft target toward the
  search's value-weighted distribution on every searched window, or no
  search in training and search at deployment only. The arms are the
  recipe of record, search off, and soft targets, at equal box time,
  behind an offline gate (the search's option ranking against K=8 rollout
  truth on un-acted windows). Priced: a week-long arm moves about 1.5pp at
  the run's slope and a 5,000-game paired read resolves 0.7pp, so the arms
  are sized before they are ordered. The soft-target arm's known hazard is
  ADR-0111's dose-scaled loss of up to 47pp. The search's wall cost was
  2.1× per game at Build 2 and is re-measured first. Ponder-time search
  follows the arms' decision.

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
- **M12:** unbuilt, with a second consumer. The search copies are
  determinized to the acting seat's information set by uniform resampling
  of hidden zones (ADR-0102); a belief head would make that sampler
  belief-weighted. ADR-0126 routes "the belief sampler for
  determinization" to the M13 scoping as a candidate. Its place depends on
  entry 2's arms: it is a deployment-time project if search leaves
  training, and it moves up if soft targets win. Two published systems
  report that uniform hidden-state sampling hurts their search (the 11-09
  design review's survey in the [running record](m12-running-record.md);
  not adjudicated here). ADR-0125 excludes randomized hidden cards from
  the value track, so the critic of entry 9 is not a consumer.

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
- **M12: largely built as surfaces, and the cast-target pointer is masked
  to the engine's legal targets.** Targets, modes, entity picks, ordering,
  damage and tuck are model-answered callbacks, and the search acts the
  (option, answer) pair (ADR-0106): the complete action is what the leaf
  judges. The union target mask
  ([ADR-0122](../decisions/ADR-0122-union-target-mask.md)) lists each
  option's legal targets and cut the illegal-pick veto class 38%. The void
  class remains: a candidate the decoder cannot plan is never valued
  (≈ 29% by count, ≈ 3% by playability; ADR-0114). So do the residual
  vetoes, 6.5% of generation attempts and 1.5% of first attempts
  (ADR-0126, done-when 1; routed to the next boundary). The named piece
  still missing from the canonical form is the late-payability scan: the
  X or sacrifice choice made before the payability test, so that X spells
  and cost-reduced commanders are offered at exact mana (ADR-0005). It is
  priced against the per-candidate target-setup cost and is not
  scheduled. Its measured size is 57 of 107,247 heuristic casts the scan
  never offered, some of them phantom (the running record, 2026-10-05).

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
- **M12:** the plan chain is gone. Credit reaches the policy through the
  V-trace policy gradient on every window and the pick-distillation loss
  on search-acted windows (ADR-0113). That gradient is close to
  Monte-Carlo: one game outcome spread over about 1,300 bridged windows,
  against a real-vis baseline that ranks contested states at 0.32 (the
  11-09 design review, finding 2). The value head is trained on outcome
  targets, which pull it off rollout truth (ADR-0118), plus an anchor to a
  fixed rollout-labelled bank. The anchor is the staged answer to "what
  anchors the leaf", and it failed in its first form: the head memorized
  the bank ([ADR-0124](../decisions/ADR-0124-anchor-bank-refresh.md)). The
  canonical answer is entry 9. The credit question re-forms as "what is
  the advantage baseline": the full-vis critic as the baseline and a
  λ < 1 return arm are M13 candidates (ADR-0126). End-to-end credit
  through the search's own leaf values stays the far endpoint and is not
  priced.

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

## 9. Value truth as a stream (the truth stream, the critic, the student)

Named 2026-10-29. [ADR-0125](../decisions/ADR-0125-value-head-track.md),
status proposed; a candidate center of M13 (ADR-0126, decision 6).

- **Now:** the value head trains on V-trace outcome targets with an
  anchor to a fixed bank of 8,403 rollout-labelled states. The bank is
  drawn at a quarter pass per iteration or less, a meter reads the gap
  between the anchor's training rows and a frozen holdout, and the run
  pauses at a gap of 0.15 (ADR-0124 §4–5). This form holds the head and
  does not improve it: the holdout ranking read 0.452 at both
  `big-run/iter-405` and `iter-513`. The full-vis critic of design §4 is
  off in the loop.
- **Canonical:** three layers. (1) Generation forks a registered fraction
  of its own games and plays K rollouts to the end; the anchor draws from
  a rolling window of those rows and a frozen slice per segment is the
  holdout. (2) A full-vis critic with its own capacity trains offline on
  the stream and on outcomes; it never serves and never chooses an action
  the policy learns from. (3) The real-vis head regresses onto the
  critic's scores after games complete. The stream stays the audit, which
  makes invariant 4 continuous. A fork copies the hidden state, so a
  rollout mean is already Monte-Carlo full-vis truth.
- **Price (ADR-0125):** about 19 worker-seconds per rollout. One K=4 label
  per four games adds about 9% to an iteration's generation, for 120 rows
  an iteration and about 12,000 a segment. Label noise at K=4 is sd 0.25
  per row. The alternative it retired, a fixed 40,000-state bank, was
  priced at 2.5 to 3.5 box-days. The build is a boundary item: the
  generation forkcheck must show a mainline with forks on trace-identical
  to the same seeds without.
- **Funds it:** each layer has a bar before the next starts, with numbers
  fixed at the track's scoping. The evidence for: every fixed truth set
  the loop has had was memorized or went stale (ADR-0124); the Ante
  ledger is critic-bound at corr(raw, ledger) 0.197 against the ≈ 0.58
  its 1.5× bar needs. The evidence against expecting strength from the
  leaf alone: the two leaf reads in entry 2 were noise at the 1pp level.
  So the critic is judged on advantage variance as well as on the leaf
  (ADR-0126). The amortized advantage head of
  [ADR-0119](../decisions/ADR-0119-value-function-first-before-the-big-run.md)
  item 4 is folded in.

## 10. A learned, in-model ability encoding

Named 2026-10-23 (the user); [m12-plan.md](m12-plan.md), "Out of scope /
routed by name". Re-deferred by ADR-0126: low priority, at the
from-scratch recipe-trimming stage.

- **Now:** each ability's vector comes from a frozen external text
  encoder (Qwen3 over the ability's text, table
  `abil-cf2ca6ba-b4s-qwen3`) and sits in the model as a fixed buffer.
  Only the projections that read it train.
- **Canonical:** one network that learns what cards do from playing them:
  an encoder over the Forge scripts trained in pre-training, or names
  only. It makes the project smaller and a reproduction independent of an
  external text model.
- **Funds it:** three tests, in order. The random-vector rung on the
  current table, which reads whether the text carries effect information
  or only identity. A learned script encoder against the Qwen3 table.
  Names only. The migration is not a cold swap: the new encoder is added
  beside the old table with a zero-initialized projection, trained in
  place, and the old path is retired after a paired read with the old
  vectors zeroed sits inside a pre-registered margin. The removal is an
  input change, so that paired read is the bridge across it. The record
  gives no box-time price.

## 11. Learned dynamics as a search accelerator

Named 2026-10-26 (the user) as a possibility, not a plan;
[m12-plan.md](m12-plan.md), same section. Re-deferred by ADR-0126: it
needs entry 10 first, and search's place in training is itself open
(entry 2).

- **Now:** every search copy is played by Forge, at tens of milliseconds
  per simulated transition. The search's wall cost was 2.1× per game at
  Build 2.
- **Canonical:** a hybrid inside search only. A learned world model takes
  the common, confident transitions of a lookahead, the engine takes the
  rare or low-confidence ones, and the value audit catches the rest. The
  engine still plays every recorded move, so no invalid game is recorded.
  Full-game dreaming is excluded at any plausible accuracy.
- **Price (10-26; order of magnitude, not measured):** about 0.14 ms per
  batched transition in an outside benchmark. Holding Forge's rules
  content takes about 20–50M parameters. Search-grade accuracy, about
  1e-4 per transition, probably takes 1–10B. Full-game precision needs
  about 6e-8 per transition at about 1,600 decisions per Commander game,
  which is out of reach by scaling.
- **Funds it:** an effect model existing (entry 10), then the first
  measurement: transition error against parameter count on our pool. The
  standing monitor is the gap between a dreamed lookahead's value and the
  engine-played returns.
