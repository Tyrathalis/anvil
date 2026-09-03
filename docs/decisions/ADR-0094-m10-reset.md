# ADR-0094: M10 reset — the planner hierarchy: binding execution, a reward-trained planner anchored by inline search distillation, strength-first reads

- **Date:** 2026-09-03 (adjudicated across 2026-09-02/03)
- **Status:** accepted — six forks user-adjudicated; the full statement
  of record is [m10-reset-draft.md](../design/m10-reset-draft.md)
- **Design-doc anchor:** m10-plan.md (doc of record) and
  m10-build-spec.md §1–§5; supersedes the ADR-0093 routed design round;
  re-frames ADR-0084's gates and ADR-0092's coupling

## Context

Probe6 ([ADR-0093](ADR-0093-m10-probe6-read.md)) was the first M10 probe
to finish its planned length and landed in the discuss-zone. At the
adjudication a label-shaped content probe (`scripts/sched_content_probe.py`)
showed the consumer's schedule-conditioned following at ≈5pp on its own
training windows and content sensitivity at ≈3%, with the live follow and
utilization headlines explained by natural-line inflation (fed = closed
on natural windows). Policy gradient never reached the emitter; the
ADR-0088 live-gap ratio ran 3.3→5.7× — the on-policy drift and the
staled-mint tell were one fact. The user adjudicated NO-FUND / no KILL
and asked for a step back on strategy before the next probe.

The step back started from four facts: the checkpoint of record
(`d6-run11/iter-019`) has not moved since 2026-08-03 across M5–M10; the
probes' proxies repeatedly measured the wrong thing (presence for
content, lumped counters for hold drift, natural-line inflation for
following); the funded ceiling (+13.5pp/game, +14.1pp on v<0.45,
[ADR-0078](ADR-0078-m10-ceiling-measurement.md)) was measured under
binding `-forceschedule` execution while the live surface was advisory;
and the recipe had accreted eight loss terms and thirteen guards with
two half-finished couplings (advisory schedule, PG-masked payment). Four
underlying issues were named: a signal-density diagnosis answered with
small fixed batches; surfaces before couplings; two action abstractions
deciding the same thing; inverted reads.

## Decision

The M10 loop is restated as a **planner hierarchy**: a turn planner whose
single action is the schedule plus implicit hold-set, decoded at MAIN1
and at each revision trigger with a log-probability; and a window
executor-reactor that owns everything else. Six forks, all adjudicated
on the drafted leans except Fork 3, which the user improved:

1. **Binding execution at serve** (Fork 1): at an own post-land priority
   window whose NEXT slot is a legal candidate, the slot is played
   without consulting the cast head (no cast log-prob; out of the cast
   PG, the auto-pay convention); a hold binds on spells for the turn;
   forced-cast vetoes are trigger 1 and attributed to the planner. The
   advisory surface's learned-fidelity follower is recorded by name as
   the deferred alternative. Adjudication principle, stated by the user
   and carried through the round: **prefer the simpler, more elegant
   architecture that lets the model act correctly and coherently, even
   at more data and training time.**
2. **A reward-trained planner with the mint anchor** (Fork 2), on
   density grounds: PG on the schedule action (emissions AND revisions;
   revisions reward-only in probe7), V-trace credit at its step,
   teacher-forced re-scoring for the ratio; the mint CE at frac 0.05
   stays the grounded anchor; planner KL guard at 0.06, entropy a read;
   E/R aux stay; learning rates unchanged.
3. **Inline certification** (Fork 3, the user's revision of a drafted
   background daemon): the generation worker certifies a sampled 2% of
   live MAIN1 windows as the game runs (rollout-label mode + a per-fork
   schedule directive over the wire); under binding the natural line is
   no longer an independent witness, so **a window is labeled only if
   rolled out and the label is the search-adjudicated best of {own plan,
   arms}**; labels and the arm Δwr spread ride the store (the replay
   window is the era weighting; the 08-30 mint stays an anchor batch
   until the in-store pool exceeds it); the mint term moves into the RL
   pass on labeled rows — grounded × dense × on-distribution by
   construction; replay parity and the labbatch mechanics leave the
   critical path. Named extension: the **pivotal-moment head**, trained
   on the arm spread, for certification yield, drill extraction, and
   live search at deployment. Verified: live forking has existed since
   M2 D4; workers 2g→4g fits (32 of 62 GB).
4. **Strength-first reads** (Fork 4): the PRIMARY probe read is a
   stratified paired strength read — candidate vs the same ckpt under
   advisory serve, K=8 paired completions from a FIXED baseline-generated
   600-window v<0.45 population, bar at the ADR-0078 threshold scale
   pinned pre-flight — with a **day-zero read** (binding execution of the
   distilled mint alone; below minus the bar = halt for adjudication,
   not auto-kill); headroom shrinkage (the ADR-0084 sweep read)
   promotion-only; KILL = the veto's first-window axes or forced-veto
   rate sustained two iterations from the 4th; content/utilization/
   follow gates, the live-gap ratio and the content probe retired as
   reads.
5. **A staged budget** (Fork 5): two build sessions + one probe, staged
   around the day-zero read — session one = binding serve rule + paired
   read + fixed population + the day-zero read on probe6 iter-5 (also
   probe7's init); mid-point rule; session two = loader action, planner
   PG + KL twin, inline certifier, smoke, pre-flight; probe7 (6×480)
   reads what training adds. Nothing on the stratum with a clean loop =
   a legitimate negative answer to M10 at the hierarchy level.
6. **Payment under the same principle** (Fork 6): DEFERRED by name to
   the probe7 read (ceiling ADR-0075, executor = the schedule-consistent
   payment scorer, trigger = the per-fork directive landing).

Retired: the follow term, the v1 plan machinery, the content/utilization
gates. Deferred by name: the own-plan follower, the contrastive term,
revision-window labels, head-only distillation of the graft.

## Consequences

- m10-build-spec's honest state: emitter DONE as a supervised planner;
  consumer PARTIAL — and moot under binding execution. The open
  question is M10's own, now posed where the ceiling was measured: does
  a distilled-then-reward-trained planner, executed as written, make
  the policy stronger on the behind stratum?
- The build order in the draft §G is the work list; the day-zero read
  is the first strength number the milestone produces.
- Standing rules born (→ standing-rules.md): a ceiling funds only the
  execution regime it was measured in; a probe's primary read is a
  strength read on the funded stratum; under binding execution the
  natural line is not an independent witness (label only rolled-out
  windows with the search-adjudicated best); design forks lead with the
  coherent architecture and stage a build around its cheapest decisive
  read.
- The CLAUDE.md M10 bullet was compressed to the archive at this
  stamp (snapshot 2026-09-03).

## Addendum (2026-09-03, session one built)

- Build status is recorded in m10-reset-draft §H. Two findings from the
  build change the reading of earlier measurements: (1) **no fork
  completion ever carried a schedule** — the server gated the carry on a
  store-indexed game id, so the ceiling's natural arm and every mint
  completion played mask-closed (not advisory); the reset's baseline is
  the first time a completion plays with the surface fed; (2) **the
  ADR-0090 decode raised on single-slot micro-batches** and fell back to
  the heuristic ~1,266 times per 480-game iteration in probe6, unseen.
- Population pin amended (user): the fixed v<0.45 population is drawn
  from the ADR-0078 ceiling census, not generated at the baseline ckpt;
  stratum critic = `d4-critic-fullvis`; `PAIRED_*` pins in
  `scripts/sched_pins.py`. Read budget 2–3 h accepted.

