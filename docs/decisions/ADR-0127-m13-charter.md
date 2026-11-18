# ADR-0127: M13 charter — what in the recipe produces the gain: an upstream merge, then three arms at equal box time read head to head against the control

- **Date:** 2026-11-18
- **Status:** accepted
- **Design-doc anchor:** §13 (sequencing); §3e (search as the behavior policy); §6 (the training loop)

## Context

[ADR-0126](ADR-0126-m12-closeout.md) closed M12 with one verdict and one open question. Training scale works: `big-run/iter-405` reads +9.46 ± 0.77pp over its era reference, network alone. What in the recipe produces that gain is not known, and the run's last segment did not improve the network.

The ADR ordered three measurements before the charter and a re-read of its routing table against them. All three closed by 11-18 ([m13-prescoping-measurements.md](../design/m13-prescoping-measurements.md)):

- **The ladder.** One rating per checkpoint fits all ten pairs. The head-to-head read resolves 0.55pp at 5,000 games.
- **The search-ranking gate.** The un-acted slope is +0.351 ± 0.073, so the soft-target arm runs. At the windows the search acts on, the slope is −0.061 ± 0.110; that is a flag at 1.9 standard errors.
- **The search's wall cost.** 5.2 times the worker time of a game. A search-off arm plays about 3.5 times the games at equal box time (*estimate*).

Two unplanned reads joined them. Generation's slots were idle 32% and 47% of its cells' wall time, draining tails. Four-player games cost 13 times two-player, and 15% of four-player rollouts through the game copier fail on upstream master.

## Decision

**M13 opens.** Its plan is [m13-plan.md](../design/m13-plan.md); the build order, done-when and kill conditions are pinned there. In brief:

1. **Build 0: the upstream merge**, alone, as the opening boundary, with its reads: the era bridge, the Monte Carlo opponent, the held-out precon read, the copier's cause.
2. **Build 1: a second fork commit** with forced-decision replay, the starting-player field and ADR-0126's next-boundary items, offered under ADR-0025's exemption.
3. **Build 2: throughput that changes no game.** One queue per iteration and across seat arms.
4. **Build 3: three arms from `iter-405` at equal box time**: the recipe of record, search off, soft targets. Each is read head to head against the control on 5,000 games.
5. **Build 4: the value-head track** ([ADR-0125](ADR-0125-value-head-track.md)) in a worktree, beside the arms. ADR-0125 stays proposed until the track's own scoping pins its bars.

**The user's pins (11-18):**

- An arm runs a week. Its bar is 2 standard errors head to head (1.1pp); inside the band it is reported as level.
- The search-off arm keeps 480 games per iteration. That confounds it with more updates; an equal-updates arm follows if it wins.
- Forced-decision replay is an M13 item.
- Straggler carry-over runs after the arms, as its own comparison.
- The play-or-draw surface lands after the arms, so the arms run on one engine.
- `Hard.ai` and `Hardest.ai` stay out of the arms' profile draw.
- The benchmark's eras, rules and reference opponents are pinned when the held-out precon read is in.
- Monte Carlo as a training opponent is decided by the merge's read of `iter-405` against it.

## Consequences

- **The kill conditions are pre-registered in the plan.** Their numbers (a 3pp drop on the era bridge, 2 standard errors on the control's mid-point read) were proposed by the drafting session and accepted with the charter.
- **ADR-0126's routing is dispositioned.** The plan's "Out of scope / routed by name" table schedules or re-defers each of its candidates with a reason. The engine benchmark, the short format and a second format are deferred; learnable stops, the generic target choosers and the untraced callbacks ride with the play-or-draw boundary.
- **A correction carried in.** One queue per iteration does not recover the 30 to 39% of generation wall quoted on 11-18; that is the continuous queue's figure. One queue leaves one drain per iteration. Carry-over removes it.
- **No standing rule is born here.**
- **Numbers are not compared across the merge.** The era bridge is the only link between M12's figures and M13's.
- **The Now block's between-milestones bullets move verbatim to the status archive**, and M13's running record opens.
