# M10 reset — DRAFT for adjudication (session 2026-09-02, the step-back round)

Session: the probe6 adjudication ([ADR-0093](../decisions/ADR-0093-m10-probe6-read.md)
addendum). The user adjudicated probe6 NO-FUND / no KILL and asked for a
step back before the next probe: are there underlying issues in the
strategy, and is there a more canonical version of the plan? This
document is that step back. It restates the M10 loop as a planner
hierarchy, moves execution to the regime the ceiling was measured in,
makes the certifier the loop's signal source, inverts the probe reads,
and lists what retires. Six forks with drafted leans; the learned-
fidelity follower is recorded by name as the deferred alternative.
**Fork 1 ADJUDICATED 2026-09-02 (user): binding execution, all three
sub-pins.** Forks 2–6 pending.

Adjudication principle, stated by the user at Fork 1 and carried into
the remaining forks: **prefer the simpler, more elegant architecture that
lets the model act correctly and coherently, even when it costs more
data and training time.**

## A. The facts the step back starts from

1. **The checkpoint of record is `d6-run11/iter-019`, promoted
   2026-08-03.** M5, M6, M7, M8, M9 and the six M10 probes have all
   closed as ties, no-promotion, or competency-without-strength. A month
   of loop and instrument building has moved the strength number by
   zero. Each milestone answered a real question; none moved the prize.
2. **The proxies have repeatedly measured the wrong thing**: presence
   for content (ADR-0084/0087), lumped serve counters for hold drift
   (ADR-0091, retracted), and — found at the probe6 adjudication —
   natural-line inflation for following and utilization.
3. **The probe6 label-shaped content probe** (`scripts/sched_content_probe.py`;
   the certified arm fed at the 496 windows the follow term trains on,
   the natural line fed at 539 windows it never trains on, slots 0 and
   1 swapped = a legal-candidate content change):

   | ckpt | certified: follow fed / closed | swap-flip | natural: follow fed / closed | swap-flip |
   |---|---|---|---|---|
   | init | 9.7% / 9.1% | 0.0% | 67.0% / 67.9% | 0.0% |
   | iter-2 | 12.3% / 10.1% | 2.5% | 69.9% / 68.5% | 2.9% |
   | iter-5 | 19.0% / 14.1% | 2.8% | 65.3% / 66.4% | 2.9% |

   On natural windows the schedule adds nothing (fed = closed within
   noise); the 32–52% live follow rate is the policy playing its own
   line. On the training windows themselves, schedule-conditioned
   following is ~5pp and half the follow term's effect is behavior
   cloning of certified first casts. Content sensitivity is ~3% on
   label-shaped inputs and ~0.6% on the pinned day-zero population
   (86% six-slot, 36% one card repeated six times) — a fair miss of the
   0.02 bar on either population, not an instrument artifact.
4. **Policy gradient never reaches the emitter.** The only learner use
   of the schedule logits outside the mint term is the grad-free live-CE
   telemetry (`rl.py` sched aux block). The emitter is a supervised
   planner distilling a frozen 08-28/29 mint; the live-gap ratio
   (`sched_live_ce / seedlab_raw_step`) read 3.3 / 3.1 / 3.5 / 3.8 /
   4.9 / 5.7 across probe6 — above the ADR-0088 3× tell throughout and
   climbing. "Drifting apart" and "staled mint" are one fact.
5. **The regime mismatch.** The funded ceiling (+13.5pp/game, +14.1pp on
   v<0.45, [ADR-0078](../decisions/ADR-0078-m10-ceiling-measurement.md))
   was measured with the engine-side `-forceschedule` executor: the arm
   was played as written. The live surface is advisory (slot tokens
   perturb attention; the cast head may deviate silently). Six probes
   have been learning binding execution through attention tokens and a
   496-window batch — the hard road to something the serve path does
   for free. Purposeful passing is the advisory design's worst case:
   following a hold means learning the absence of an action.

## B. The four underlying issues

1. **A signal-density diagnosis answered with small fixed batches.**
   ADR-0049 found signal density is the binding constraint; the
   responses since have been 170, 543, 2,157 and 496 windows at frac
   0.05 under a memorize guard, and a standing rule (ADR-0087) already
   says such a batch cannot carry a channel. The canonical answer is
   search distillation at scale: the search produces dense on-policy
   targets every iteration and the network distills them. Every piece
   exists here (forkable seeded engine, rollout certifier, forced
   executor, Grindstone's economy); what is missing is running the
   certifier continuously as a background labeler with era-weighted
   labels instead of as an offline mint at per-era cadence.
2. **Surfaces before couplings, and the accretion that follows.** The
   probe6 recipe carries eight loss terms (PG, value, entropy, §6c
   penalty, sched E/R, seedlab, follow, paylab) and thirteen guards,
   plus instruments whose floors must be banked pre-probe. Five of six
   probes ended on a self-inflicted layer. Two half-finished couplings
   sit side by side: the payment head has stayed PG-masked through all
   of M10 (its unmask conditions never met), and the schedule is
   advisory.
3. **Two action abstractions deciding the same thing.** The window-level
   cast head and the turn-level schedule both choose casts; everything
   hard about M10 has been arbitrating between them.
4. **Inverted reads.** Probes read competency proxies and defer strength
   to a 2,000-game closeout; 480 games/iteration cannot see strength,
   but the ceiling's own stratified paired instrument can.

## C. The canonical shape — the hierarchy statement

**Turn planner.** One learned component whose action is the turn's
schedule: an ordered list of ≤6 casts plus the implicit hold-set
(m10-build-spec §1 verbatim), decoded at the first own MAIN1 window and
re-decoded at the four revision triggers. The action carries a
log-probability (the autoregressive slot decode under the ADR-0090 stop
rule) and is trained by reward AND by distillation from certified
labels. Its degrees of freedom are exactly the milestone's goal:
ordering, and purposeful passing (a hold IS a decision).

**Window executor-reactor.** The existing cast/combat/target/trigger
policy, which now owns everything the planner does not: land drops
(the executor's land-first convention, as in the mint), off-plan
windows, combat, targets, triggers, off-turn windows, payments (still
masked), and the revision decision through the four triggers.

**Binding execution.** At an own priority window where no land play
remains, if the NEXT slot's (e, sa) is a legal candidate, it is played
without consulting the cast head. The forced answer carries no cast-head
log-prob and drops out of the cast PG (the auto-pay convention). A NEXT
slot that is not a legal candidate at a post-land window is trigger 1
(the slot failed) — a revision, not a silent deviation. A pure-hold
schedule is binding on spells for the turn (abilities and lands stay the
executor's). Deviation becomes structured (a revision, telemetry
first-class) instead of silent.

**What this removes by construction:** the consumer problem, the follow
term, the content-flip / argmax-flip / reliance instruments as gates,
the utilization floor, the follow rate. What remains to learn is
planning — the emitter — and the read becomes the one already pinned:
strength on the behind stratum.

## D. Forks (drafted leans in bold)

### Fork 1 — execution coupling

**Lean: binding execution at serve (§C).** Alternative, recorded by name
(§F.1): keep the advisory surface and learn fidelity with a dense
own-plan follow term. Sub-pins for the lean:
- Post-land binding only (the follow-window retiming of ADR-0092
  carried over: 133/232 certified windows had a land drop before the
  first spell; forcing seq[0] at the emission window would skip it).
- Hold is binding on spells. Reason: purposeful passing must be a
  reward-visible planner decision; an "abstain to the executor" class
  would be a reward-neutral degenerate the planner could hide in. The
  day-zero planner distills the natural line (full-support labels), so
  binding hold at day zero ≈ natural play; the veto watches first-window
  pure-hold > 25% absolute.
- Forced-cast vetoes (the engine rejects the forced play) are trigger 1
  and attributed to the planner (§6c's veto penalty applies to the
  planner's action at that window, not to the cast head).

**ADJUDICATED (user, 2026-09-02): binding execution with all three
sub-pins, on the principle above.** The tradeoff as discussed, recorded
so it does not have to be re-derived:

- The objection to binding is "no plan survives contact with the enemy."
  But the revision mechanism is already built and orthogonal to this
  fork: revise-on-trigger at the four engine-detectable events (slot
  vetoed, any opponent action resolved during our turn, end of turn,
  exhausted), with unprovoked revision structurally impossible (user pin
  2026-08-27). Advisory coupling adds a SECOND channel on top — silent
  deviation by the cast head between triggers — and the fork is whether
  that channel earns its keep. It does not: it lets a different component
  absorb fragility, so the planner never pays for it and never learns
  robustness.
- Binding is cheaper here than it sounds because of the plan's scope:
  own-turn casts only (off-turn windows carry no schedule; hold-up is
  the hold-set's job). Own-turn interaction is almost entirely reactive
  — counters and removal in response to a cast — and arrives as trigger
  1 or trigger 2, both wire-visible.
- What binding buys: fragility becomes reward-visible. A plan that dies
  at the first counterspell costs a turn, and a reward-trained planner
  learns plans that survive (bait first, hold mana, sequence around the
  likely response). "Put the implication of interaction into the plan"
  is what this produces, learned rather than designed; an explicit
  contingency language is a later extension of the planner's action.
- What binding costs, both promoted to pre-flight items: (1) **trigger-
  detector misses** — trigger 2 is an honest approximation (rolling
  wire-history non-self signature); under binding a missed interaction
  plays a stale plan until the next trigger. Illegality self-corrects
  (the NEXT slot is legality-checked at every own window; failure is a
  revision); the residual is a slot still legal but now wrong — the
  missed-trigger residual becomes a load-bearing read (Fork 4).
  (2) **Revision windows are the least-supervised decodes** — the mint
  labels the MAIN1 emission window; a revision decodes from a partially
  executed state and is trained only by reward. Binding makes revisions
  matter more; labeling post-interaction states is a named certifier
  extension (Fork 3), a cost item not a design problem.

### Fork 2 — planner training

**Lean: PG on the schedule action with the mint CE as the anchor.**
- The emission (and each revision) is an action at its window: the mu
  row records the sampled slots and their log-probs (`sched.lp`);
  the loader re-scores the recorded slots teacher-forced through the
  head at the current parameters for the V-trace ratio; advantages are
  the trajectory's at that step (the critic unchanged).
- Anchor: the mint term at frac 0.05 with the ADR-0088 mechanics
  verbatim (lab-k, warmup, carry-w, memorize guard), on the era-weighted
  label pool of Fork 3. This is the ADR-0085 standing rule's "grounded
  anchor of comparable mass", by construction.
- Why the ADR-0085 fixed point does not recur: that term was a decode
  aux on its own emissions, where empty was the min-CE hedge and cost
  nothing. Under binding execution an empty schedule is a real hold,
  reward-visible; under PG the planner learns whether plans help. The
  degeneracy veto's first-window axes stay armed.
- Keep: E/R aux (cheap, measured, funded at ADR-0079). Retire: the
  follow term (Fork 1 makes it moot), the v1 plan machinery (already
  off), the contrastive term (never built).
- Planner KL guard: a KL between generating and current planner on
  emission rows, the cast head's `guard_kl` twin, pinned at pre-flight.
- Alternative (recorded): supervised-only planner + re-mint cadence
  (the probe6 loop with binding execution). Cheaper, but the planner
  then never learns from outcomes and the goal is not addressed.

### Fork 3 — the certifier as the loop's signal source

**Lean: an asynchronous background labeler with era-weighted labels.**
- Each iteration, sample K windows from the latest accepted store and
  certify them on the generating ckpt (sampled serve, `--fork-instrument`,
  the witnessed-parity discipline of ADR-0088/0089 verbatim; the
  generating-ckpt server stays up one extra iteration, the ADR-0089
  phased-lane pattern). Labels append to a pool stamped with era =
  generating iteration; the mint term samples the pool with recency
  weights (lean: last 4 accepted iterations at equal weight, older
  eras at 0 — pin at pre-flight; the live-gap ratio becomes the
  re-weighting instrument instead of a cliff).
- Pricing from the banked bench (44 s wall/window at 8 lanes): 8 lanes
  ≈ 60 windows per 45-min iteration, 12 lanes ≈ 90 — a trickle at the
  28% certification yield (~20 labels/iteration), so the first probe
  runs mostly on the 08-30 mint (2,157 full-support labels, era 0) plus
  the trickle. The point of building it now is the mechanism: staleness
  becomes a weighting input, and the per-era re-mint (24 h) becomes
  the batch fallback rather than the only clock.
- Lane budget: the certifier runs at nice 19 beside generation; if the
  box cannot carry both, the certifier yields (generation is the
  critical path). Full-support labels (certified arm + natural casts)
  are minted per window exactly as `mint_full_support.py` does.
- Alternative (recorded): per-era re-mint only (the current cadence).
- **Named extension (from the Fork 1 adjudication): revision-window
  labels.** The certifier forks at any window; certifying arms from the
  post-interaction state at trigger windows (sampled from live revision
  rows) gives the planner grounded supervision where binding makes it
  matter most. Not in probe7's budget unless the emission-window
  labeler lands early; priced by the same 44 s/window bench.

### Fork 4 — the reads (inverted)

**Lean: the primary probe read is a stratified paired strength read.**
- Population: ~600 fresh-seed turns from a sweep-shaped run at the
  candidate ckpt, binned by the eval critic at v = 0.45 (the ADR-0078
  competency-read population, verbatim). Pairing: from each window,
  play out the terminal ckpt vs the init ckpt with the same seeds, K
  rolls, both seats' decisions from the same state — the ceiling's own
  instrument with the candidate policy in place of the forced arm.
  Report mean Δwr on the v<0.45 stratum against the banked +14.1pp
  scale; the FUND bar sits at the ADR-0078 threshold scale (the ~2.2pp
  per-game equivalent), exact number pinned at pre-flight.
- Secondary (exploratory, never gating): first-window hold / length /
  revision rate; forced-cast rate and forced-veto rate (the invalid-
  schedule family — the "void arms are free" derivation was under the
  advisory executor and must be re-read under binding); planner KL;
  mint CE by label class (certified vs natural — a split the probe6
  read lacked); live-gap ratio re-based on the full-support batch; the
  label-shaped content probe as telemetry.
  **Missed-trigger residual** (from the Fork 1 adjudication): the rate
  at which an opponent action during our turn resolves without a
  trigger-2 revision (the canonical-register instrument's territory);
  under binding it is the rate at which stale plans play out.
- Retired as gates: content_flip, argmax_flip, reliance_l1, utilization
  floor, follow rate, follow CE. The pinned day-zero population's
  schedules are garbage-shaped and the surface is no longer advisory.

### Fork 5 — probe shape and budget

**Lean: m10-probe7 = the reset recipe at D4 shape (6×480), on a fixed
budget: two build sessions + one probe.** Pre-registered outcomes:
- FUND: the stratified read clears its bar with the veto clean.
- KILL (auto, from the 4th accepted iteration): first-window pure-hold
  > 25% or mean length < 1.0 sustained two iterations (the veto,
  absolute), OR forced-veto rate above a pre-flight bar sustained two
  iterations.
- Nothing on the stratum with a clean loop = **a legitimate negative
  answer to M10 at the hierarchy level**; the milestone may close on it
  with the assets carried. The reset must not become another month of
  infrastructure.

### Fork 6 — payment under the same principle (named, not decided)

The schedule-consistent payment scorer (ADR-0078's engine asset) could
execute payments for scheduled casts the way binding execution executes
the casts, retiring the PG-masked pay path or re-basing its unmask
conditions. **Lean: defer until probe7 reads; record here so it is not
lost.** The ADR-0075 fact (+2.96pp as a supervised conditional
competency) is the ceiling this fork would go after.

## E. Retirement list

| item | disposition |
|---|---|
| follow term (`--follow-frac`, `follow_pass`, `guard_follow_share`) | RETIRE (Fork 1) — code kept for §F.1 |
| content_flip / argmax_flip / reliance_l1 gates; utilization floor; follow rate/CE reads | RETIRE as gates; `sched_reliance.py` stays telemetry |
| v1 plan machinery (`--plan`, plan reliance, `guard_plan_share`) | already off; strip from the recipe |
| seedlab term | KEEP as the mint anchor on the era-weighted pool |
| E/R aux, `guard_sched_share/spike` | KEEP |
| paylab + pay mask + PG-unmask conditions | KEEP unchanged; Fork 6 names the alternative |
| KL guard (cast head) | KEEP; add the planner twin |
| degeneracy veto | KEEP, first-window axes, absolute |
| §6c veto penalty | KEEP; forced-cast vetoes attributed to the planner |
| memorize / share guards on fixed batches | KEEP (one fixed batch remains) |
| per-era re-mint | becomes the batch fallback behind Fork 3 |

## F. Deferred alternatives, recorded by name

1. **Learned fidelity (the advisory design's follower).** A dense
   own-plan follow term at live post-land windows: feed the policy's
   own carried schedule, CE on the priority pointer toward the NEXT
   slot when it is a candidate; gradient-stopped at the plan (the plan
   is a sampled discrete object, so the emitter is not in the graph);
   frac 0.05, ADR-0088 mechanics; reads = live follow rate and
   `sched_live_ce` reversing, swap-flip on certified windows well past
   3%. This is probe1's mechanism minus the self-reference and is the
   test of whether soft conditioning can reach high fidelity at all.
   Revisit if binding execution turns out to need a soft escape hatch
   between triggers.
2. **Contrastive two-arm follow term** (ADR-0093 routing) — moot under
   binding execution; kept by name.
3. **Label-shaped content read** — built (`scripts/sched_content_probe.py`);
   telemetry only under the reset.

## G. Build order and hazards

Build order: (1) serve rule in `sched_serve.py` + the server answer path
(forced answers flagged in the mu row, no cast logp; emission/revision
rows gain `sched.lp`); (2) loader: the schedule as a scored action at
its window; (3) learner: planner PG term + planner KL guard; follow term
off; (4) certifier daemon: per-iteration window sampling + certification
on the generating ckpt + era-stamped pool + recency weights in the mint
batch builder; (5) the stratified paired read as a driver-callable
script (the ADR-0078 binned-read machinery with a policy in the arm's
place); (6) 4-game smoke: forced execution parity with the mint
executor's semantics (land-first, post-land binding), carry tripwire 0,
forced rows carry no logp; (7) day-zero banks + pre-flight pins + launch.

Hazards to pre-register:
- The cold-start poison wave (8 workers × 1 first request) now lands on
  a binding surface — per-iteration warm-up forward before generation.
- Forced casts bypass the cast head's veto penalty: attribution to the
  planner must be in place before launch or vetoes become free again.
- The certifier and generation contend for the box; the certifier
  yields. Anchor timelines on artifacts, not on the plan.
- Suite: `seedlabels`, `sched_serve`, loader parity, and the forced-row
  PG exclusion each need a regression test from the real probe6 rows.
