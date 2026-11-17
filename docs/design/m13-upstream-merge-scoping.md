# The M13 upstream merge — scoping draft

**Doc status:** living · scoping of the upstream merge that opens M13: its size, the Flat Monte Carlo heuristic mode, and the opponent question; three points pinned by the user 11-16, one revised 11-17; the count budget is built locally, nothing merged

Drafted 2026-11-16 from a read of `upstream/master` at `0f82b4f469` (2026-11-17 UTC). Nothing was merged or checked out; the trial merge ran in memory. The facts about Flat Monte Carlo come from reading its code, not from running it.

## Pinned by the user, 2026-11-16

- **The merge happens inside M13, as its opening boundary, after the design.**
- **The rollout-count budget is built before the merge**, on upstream master, and queued early on the upstream list ([upstream-worklist.md](upstream-worklist.md), Tier 0.10). The merge's reads run only on a jar that has it.
- **The announcement's Monte Carlo opponent is the desktop mode at a count budget matched to what an idle desktop achieves** (the user, 11-17; it replaces the 11-16 pin of the unstarved allowance). The reason: a desktop is already above the average machine running Forge, and the unstarved allowance is far beyond what any player meets. Beside the plain-heuristic read it also shows how much the heuristic has improved.

The open questions at the end are still open.

## Summary

- **The merge is large in commits and small in conflicts.** Upstream is 1,340 commits past our merge base (`97535e047f`, 09-16). Seven files conflict textually, three of them from our own determinism PR that upstream merged in its own form.
- **The heuristic has changed a great deal.** 131 of those commits touch `forge-ai`. `AiController.java` alone gained 1,645 lines.
- **Flat Monte Carlo is on by default for players and off by default for us.** It is a game-level switch that only the GUI's match setup turns on. Our harness builds its own games, so after the merge the heuristic plays without it unless we set the flag.
- **Its budget is wall-clock, which is the problem.** As served it gets 1.5 s per decision and 6 s per turn on desktop. Its strength therefore depends on how loaded the box is, and its games are not seed-reproducible.
- **Proposed:** report against both opponents; train against the plain heuristic unless a measured read says the Monte Carlo opponent teaches more per box-hour; and add a rollout-count budget so the Monte Carlo opponent can be measured reproducibly.

## The size of the merge

| | Upstream since 09-16 | Ours since 09-16 |
|---|---|---|
| Commits | 1,340 | 119 |
| Files changed | 6,611 (mostly card scripts) | 78 |
| Files changed on both sides | 21 | 21 |

**Textual conflicts (7):** `AiBlockController.java`, `AiController.java`, `GameCopier.java`, `MyRandom.java`, `SimulateMatch.java`, and two test files. `MyRandom.java` and the two tests are our determinism hooks meeting upstream's merged version of the same PR (#11285); upstream's form should win and our delta shrinks.

**The semantic risk is larger than the textual one.** These files merge cleanly or nearly so, and each carries something we depend on:

| File | Upstream change | What of ours rides on it |
|---|---|---|
| `GameCopier.java` | +193 lines | every search copy and every rollout fork; the fork-fidelity rate (48 divergent per 500) is measured against the old copier |
| `PlayerControllerAi.java` | +413 | the bridge's controller overrides and every served surface's callback |
| `ComputerUtilMana.java` | +766 / −222 | the payment enumeration and the payability filter |
| `PhaseHandler.java` | +349 / −154 | the search directive's leaf events and the game-time caps |
| `AiController.java` | +1,645 | the natural line that every search and every label starts from |
| `Game.java`, `Player.java` | +161, +198 | the shuffle mark, the union target mask's reads |

The last merge of this kind was 09-16 ([ADR-0110](../decisions/ADR-0110-m12-upstream-merge-20260916.md)). Its shape applies again: a tag before the merge, the merge as one commit, the forkcheck, then a re-baseline. This one is a boundary by construction: the heuristic's play changes, so no trace-hash identity is expected.

## Flat Monte Carlo, as read from the code

- **What it is.** At a decision the AI takes up to 5 candidate plays (7 on the Hardest profile), copies the game, re-deals the cards it cannot see, and plays each candidate forward a few plays under the heuristic, 4 to 6 rollouts per candidate. It overrides the heuristic's pick on a majority of rollouts. It covers main-phase plays, land choice, mulligans, reactive plays and, on some profiles, attacks.
- **It does not cheat.** `HiddenInfoShuffler` pools and re-deals the opponent's hand and both libraries in the copy before each rollout.
- **How it is switched.** Two conditions must hold: the game flag `AI_FLAT_MONTE_CARLO` and the profile property `FLAT_MC_ENABLED` (default true). The game flag is false at construction and is set by `HostedMatch` from a GUI preference whose default is true. `SimulateMatch` has its own flag.
- **As served to a desktop player** it also sets `AI_FLAT_MONTE_CARLO_MAX`, which raises the budget to 1,500 ms per decision and 6,000 ms per turn. Mobile gets a lite mode at 600 and 2,500 ms.
- **The budget is wall-clock.** Rollouts stop at a deadline. A slow streak makes the mode sit out several turns and return with fewer candidates and rollouts. Each decision also draws its base seed from the game's own random stream.
- **New profiles.** `Hard.ai` and `Hardest.ai` exist upstream beside the four profiles our harness draws from.

Three consequences for us:

1. **Strength depends on load.** On a box running 24 workers the Monte Carlo opponent gets fewer rollouts per decision than it does on a player's idle desktop. A number measured that way is not the opponent as served.
2. **Games stop being reproducible.** Whether a rollout round runs depends on the clock, and the mode consumes the game's random stream, so the same seed can give a different game. That breaks the deterministic-replay convention for every heuristic-seat game with the mode on, and forkcheck cannot hash such games.
3. **It costs box time.** At the desktop budget a heuristic turn can take 6 s. Our median game is 27 s today. Half of the big run's training games had a heuristic seat.

## The opponent question

Three opponents exist after the merge:

| Opponent | Reproducible | Cost | What it is for |
|---|---|---|---|
| **Plain heuristic** (the flag off) | yes | about today's | the continuity opponent: the closest thing to what M12 measured against |
| **Monte Carlo as served** (the flag on, desktop budgets, wall-clock) | no | high, and load-dependent | the number players will ask about |
| **Monte Carlo on a rollout-count budget** (not built) | yes | fixed per decision | a reproducible stand-in for the served mode |

**Proposed for evaluation: report both.** The plain heuristic stays the era-to-era scoreboard, beside the ladder. The Monte Carlo opponent is the second, harder number. Until the count budget exists, the as-served read runs at a load low enough that the budget is not starved, and it records the rollouts actually achieved per decision from upstream's own `FlatMonteCarloStats`.

**Proposed for training: decide by measurement, with the plain heuristic as the default.** The user's concern is right: turning the mode off means training against something other than the heuristic as served. Three things bear on it.

- Training does not need the opponent players face. It needs opponents that teach. Half the games are already self-play.
- A wall-clock opponent in generation makes the training data depend on box load, which no run so far has had to account for.
- The cost may be worth it if the stronger opponent teaches more per box-hour. That is measurable.

**The count budget is worth building, and worth offering upstream.** A property that caps rollouts by count and ignores the clock would make the mode reproducible for us and for upstream's own tests, one of which already notes a verdict that changed from run to run with the time budget. It fits the project's rule that budgets are in evaluations, never wall-clock, during training.

## The reads the merge needs, in order

All after the merged jar builds and the bridge's hooks are confirmed on it.

1. **The forkcheck on the merged jar**, flag off. Not for identity; for crashes and for the copy-fidelity rate on the new `GameCopier`.
2. **Plain heuristic, new against old.** `iter-405` and the era reference against the plain heuristic on the merged jar, paired on the 11-07 confirm's seeds. This is the era bridge and M13's day-zero.
3. **Monte Carlo on against off, heuristic seats only.** No GPU. It gives the mode's strength over the plain heuristic and its wall cost per game at our load and at a low load.
4. **`iter-405` against the Monte Carlo opponent.** The second announcement number.
5. **If training against it is still in question:** one short generation cell with the Monte Carlo opponent in the heuristic seat, for games per box-hour.

## Open questions for the M13 scoping

- Does the merge bundle the routed next-boundary items (ADR-0126's table) and forced-decision replay, or land alone first? One boundary is cheaper to prove; a bare merge is easier to debug.
- Do `Hard.ai` and `Hardest.ai` join the profile draw? They change the opponent mix even with the mode off.
- ~~What the desktop allowance is in counts.~~ Answered 11-17, below.

## The count budget, as built (2026-11-17)

The patch exists locally: `FLAT_MC_COUNT_BUDGET` on branch `flat-mc-count-budget` in `../forge-upstream` ([upstream-worklist.md](upstream-worklist.md), Tier 0.10). What it settled:

- **The desktop mode's counts are the same for Default, Hard and Hardest.** At most 17 candidates per decision and 14 rounds, so at most 238 rollouts per decision, plus up to 84 for the attack search and 42 for land choice. The plain mode allows 66 (Default), 96 (Hard) and 130 (Hardest).
- **Unstarved, the desktop allowance is far more than the clock grants.** One four-player game under the count budget averaged 12.1 rollouts per decision after pruning, with a median decision of 1.6 s and a 95th percentile of 14.8 s. The clock grants 1.5 s. The pinned announcement opponent ("the desktop allowance, never starved") is therefore stronger and several times slower than the opponent a player meets.
- **The AI timeout acts in harness-built games.** `Game.AI_TIMEOUT` defaults to 5 s and every heuristic session arms it, with or without the mode. The property lifts it only for a seat that has the property; a strict read also raises the game's timeout and gives every seat the profile.
- **Three rollout errors switch the mode off for that player for the rest of the game.** With the copier failures of the cost measurement (a quarter of four-player rollouts on the 11-10 jar) that breaker matters. The patch's own four-player checks on 11-17 master saw no such failure in about 8,500 rollouts, so the failures are either fixed upstream since 11-10 or specific to some precons. Not resolved; the user's expectation is that they were always tied to specific cards and may well be fixed.
- **Heaps of 768 MB or less silently turn the desktop mode into the mobile one.**
- **Stock upstream replayed a two-player game identically on an idle box.** The clock breaks replay only when it binds.

**Decided 11-17 (the user): a count budget matched to an idle desktop.** The calibration is a step of the merge's reads: play the desktop mode on the clock with one JVM on an idle box, read its achieved rounds and candidates per decision from `FLATMC-STATS`, and set the counts to that. The cost measurement's cells give a first figure under a light load: 7.95 rollouts per decision two-player and 5.46 four-player, against a ceiling of 238.

## Not yet looked at

- What the other 130 `forge-ai` commits change in the plain heuristic. A changed plain heuristic moves the continuity number even with the mode off.
- Whether upstream's new AI timeout tracker (`AITimeoutTracker`) is active in a harness-built game.
- The playable fork's side of the merge, which carries its own patches.
- Any card-script change that touches the pool's 1,701 cards.
