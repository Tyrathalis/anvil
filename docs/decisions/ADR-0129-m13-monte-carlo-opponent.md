# ADR-0129: the Monte Carlo opponent: a per-seat switch on the harness, a count budget of 8 rounds calibrated to an idle desktop, and its strength over the plain heuristic (+9.32 ± 0.77pp)

- **Date:** 2026-11-19
- **Status:** accepted (the calibration rule is the user's, 11-17; the switch is offered under ADR-0025's exemption with its proof below)
- **Design-doc anchor:** §9 (fork discipline, seeded replay); [m13-plan.md](../design/m13-plan.md) Build 0, step 3; [m13-upstream-merge-scoping.md](../design/m13-upstream-merge-scoping.md)

## Context

Upstream's heuristic has a Flat Monte Carlo mode that the GUI turns on for players and our harness leaves off. Its budget is wall-clock, so its strength depends on box load and its games do not replay. The merge carried a count budget (`FLAT_MC_COUNT_BUDGET`) that plays every allowed round and ignores the clock. The user pinned the announcement opponent on 11-17: the desktop mode at a count budget matched to what an idle desktop achieves. Build 0's step 3 owed three things: the switch, the calibration, and the mode's strength and cost against the plain heuristic. ADR-0128 also routed here the question of whether the AI deadline binds under generation load.

## Decision

1. **The harness has a per-seat Monte Carlo switch** (fork `e40ba17c9c`, the pin). `-mc on|max` turns the mode on for the seats in `-mcseats` (default: the seats outside `-bridgeseats`). `-mcprops K=V,...` overrides profile properties for those seats through an in-memory derived profile. `-mcdecisions` writes one row per decision (mode, lines offered and sampled, rounds, rollouts, time). `-mcclock` extends the wall crash guard (default 1,800 s). The game flag stays off; the switch sets the controller's override, so a seat without it plays the plain heuristic.
2. **The switch is inert when absent.** Its forkcheck (`data/forkcheck/run-20261118-mcswitch`) matched the era's baseline 500 of 500, fidelity 467 / 33 / 0. It is not a boundary.
3. **The count budget is 8 rounds** (`FLAT_MC_ROLLOUTS_PER_CANDIDATE=5`, `FLAT_MC_EXTRA_ROUNDS=3`), with the desktop mode's other counts unchanged. The full property string is `count_props 8` in `scripts/m13_mc.sh`. This is the Monte Carlo opponent of record.
4. **Its strength over the plain heuristic is +9.32 ± 0.77pp**, paired on seed (4,991 pairs). It wins 0.5903 ± 0.0070 of its games against the plain heuristic.

## Evidence

**The calibration** (`data/runs/m13-mc/clock`, `ladder`; 40 games each on one seed set, Monte Carlo in both seats, one JVM per cell with a 4 GB heap). The clock cell ran alone under `--quiet-box` at a load of about 1.

| Cell | Rollouts per decision | Main-phase rounds | Decision ms, median / p95 | Game s, median / mean |
|---|---|---|---|---|
| Desktop mode on its clock, idle box | 8.95 | 3.64 | 284 / 1,504 | 29.0 / 40.9 |
| Count budget, 2 rounds | 5.96 | 1.94 | 277 / 2,347 | 20.8 / 77.0 |
| 3 rounds | 6.27 | 2.11 | 255 / 3,096 | 25.9 / 69.1 |
| 4 rounds | 7.57 | 2.63 | 341 / 6,977 | 24.9 / 162.7 |
| 5 rounds | 6.07 | 2.86 | 179 / 2,124 | 25.0 / 58.3 |
| 6 rounds | 8.42 | 3.25 | 320 / 3,052 | 26.9 / 102.2 |
| **8 rounds** | **9.00** | **3.69** | 343 / 3,317 | 33.6 / 76.4 |
| 10 rounds | 9.98 | 4.07 | 359 / 4,451 | 39.7 / 119.4 |
| Desktop counts (14 rounds) | 11.38 | 5.00 | 305 / 4,066 | 40.2 / 118.2 |

- Most decisions end at two rounds by pruning; a tail runs to the cap. On the clock 7% of main-phase decisions reached 14 rounds.
- The ladder is noisy at 40 games (the 5-round rung reads below the 4-round one). The 8-round figure was confirmed on the read's 197,117 decisions: 8.91 rollouts per decision, 3.42 main-phase rounds.
- The instrument holds. The desktop counts through the max flag and through profile properties gave the same game in 40 of 40, with identical decision rows. `Config.maximized()` only raises counts, so lower counts need the properties.
- The ladder's nine cells ran side by side, so their times overstate the cost. Their rollout counts do not depend on time.

**The read** (`data/runs/m13-mc/read/read.md`; seeds 20261120, the era bridge's deck pairs, 24 workers, 2 GB heaps, heuristic seats only). A win is a win over all games, so draws and crashes count against the seat.

| Arm | Games | Monte Carlo seat wins | Paired against the plain mirror | Rollouts per decision | Game s, median / mean |
|---|---|---|---|---|---|
| Plain mirror | 2,500 | seat 0: 0.4992 ± 0.0100 | | | 7.6 / 10.2 |
| Count budget, 8 rounds | 4,991 | **0.5903 ± 0.0070** (seat 0: 0.5759, seat 1: 0.6047) | **+9.32 ± 0.77pp** | 8.91 | 41.5 / 100.5 |
| Desktop mode on its clock, under the fleet's load | 1,000 | 0.5770 ± 0.0156 | +7.80 ± 1.74pp | 5.26 | 41.4 / 47.5 |

- **The clock starves under our load.** At 24 workers the desktop mode got 5.26 rollouts per decision against 8.95 on the idle box, and no main-phase decision reached the round cap. Its strength read is 1.5pp below the count budget's, inside the noise of 1,000 games.
- **The count budget costs about ten times a plain game.** The arms ran at about 740 games per hour against the plain mirror's 7,400. The mean is tail-driven: the 95th-percentile decision took 8.4 s, and the clock's deadline is what removes that tail on a desktop.
- **The AI deadline does bind under load, rarely.** 44 "AI eval thread at timeout" lines in the plain mirror's 2,500 games, 19 in the count arms' 4,991, 9 in the clock arms' 1,000. This answers ADR-0128's routed question.
- **Draws rise with the mode:** 102 in 4,991 games (2.0%) against 7 in 2,500 (0.3%). They count against the Monte Carlo seat here.

## What is not clean

- **18 workers died of `OutOfMemoryError`** in the count arms on a 2 GB heap; the ladder's 4 GB cells had none. The harness replayed their games. Nine games of 5,000 are missing; they move the winrate by at most 0.18pp.
- **Crashes in the read:** `SacrificeEffect` (24 games of 8,491, already routed to Build 1), two wall-guard timeouts, one `NullPointerException`, one `StackOverflowError`.
- **Rollout failures.** In the clock cell 114 of 24,486 rollouts failed: 84 on the copier's "Couldn't map" for a token, 7 on `SacrificeEffect`, 2 on a `NullPointerException` in `getDividedValue`. Three failures switch the mode off for that player for the rest of the game.
- **The report's exit status did not reach the run.** The report crashed on a line cut by a dead worker and the run still read `done`. The report now skips cut lines and counts a decision row only where its worker finished the game.

## Consequences

- **The fork pin moves to `e40ba17c9c`.** The serving jar for the Monte Carlo reads is `data/runs/m13-mc/forge-m13-mc-switch.jar`. Unsearched games are unchanged, so `forge-merge-20261118-bridgefix.jar` remains valid for everything else.
- **Step 4 runs against the 8-round count budget**, `iter-405` in one seat and the Monte Carlo heuristic in the other. It needs heaps of 4 GB. At this read's cost, 5,000 games take about 7 box hours; it is sized for the user before it launches.
- **The cost bears on pin 7.** A Monte Carlo seat in generation costs about ten times a plain heuristic game on the count budget, before any gain in teaching. Step 4's read decides.
- **Routed to Build 1,** with the crashes already there: the copier's "Couldn't map" on tokens, the `getDividedValue` `NullPointerException`, the `StackOverflowError` game. **Routed to Build 2:** the driver's report step failing without failing the run.
- **Upstream:** the decision listener and the per-decision counts on `Result` are small and general; they queue behind the count budget (Tier 0.10) and are not expedited.
- No standing rule is born.

## Addendum, 2026-11-19: step 4, `iter-405` against the Monte Carlo opponent

**`iter-405` is level with the Monte Carlo opponent: 0.5099 ± 0.0071 on 4,995 games, network alone.** Against the plain heuristic on the same seeds it reads 0.6064 ± 0.0069 (the era bridge's arms). The paired difference is −9.12 ± 0.78pp on 4,882 seeds. The opponent's own margin over the plain heuristic was +9.32 ± 0.77pp, so the two reads agree on its strength.

The read (`data/runs/m13-mc/ckpt/mcck.md`; `scripts/m13_mc.sh ckpt`): the era bridge's seeds (20261107), 2,500 games per seat, masked, raw, the heuristic seat on the 8-round count budget, the Monte Carlo jar, 24 workers with heaps capped at 3 GB.

- **A win is a win over all games.** 73 games were drawn (1.5%) and 10 crashed; both count against `iter-405`. The opponent won about 47.3% of the games.
- **The budget held:** 9.07 rollouts per decision on 172,452 decisions, 3.50 main-phase rounds.
- **A game costs 4.2 times a plain one:** mean 70.5 s against 16.8 s in the era bridge's arms (median 37.1 s against 14.9 s). The read ran at about 950 games per hour over its 5.2 hours.
- **11 workers ran out of memory at the 3 GB cap** (18 at 2 GB in step 3, in a comparable number of games). Five games of 5,000 are missing. The fleet held about 50 GB with 12 GB in compressed swap.
- **Crashes:** three `StackOverflowError` games, three `NullPointerException`, three `SacrificeEffect`, one wall-guard timeout. The battery reports no anomaly.

**What it means for pin 7.** The opponent is strong enough to teach: the network does not beat it. A game against it costs about four times a plain heuristic game. The decision is the user's and is not taken here. The scoping's fifth read, one short generation cell with the Monte Carlo opponent in the heuristic seat for games per box-hour, is the remaining measurement if the choice is still open.

The announcement's second number is on file: `iter-405`, network alone, 0.5099 ± 0.0071 against the desktop Monte Carlo heuristic at an idle desktop's budget.

## Second addendum, 2026-11-19: pin 7 is set at 10% Monte Carlo in every arm

**The user's decision: the Monte Carlo opponent enters training at 10% of games, in every arm.** The reason given: the extra strength is valuable and the cost is high, so it is titrated. The share comes out of the heuristic-seat games, which leaves about 50% self-play, 40% plain heuristic and 10% Monte Carlo at the 8-round count budget.

- **The cost is small beside the search.** A Monte Carlo seat adds about 54 s to a game. At 10% that is about 5 s per average game: about 3% on the recipe of record's searched games (190 worker-seconds) and 15 to 20% on the search-off arm (*estimates from the step 4 read and the 11-17 cost cells*).
- **The control is no longer exactly the recipe that produced `iter-405`.** Every arm carries the same change, so the arms' comparison holds. Each arm's final checkpoint is also read against the Monte Carlo opponent.
- **The schedule.** Every iteration carries its 10%, so each training window has the same mix. The games run as whole worker slices with the larger heap cap, queued early in the iteration and interleaved a few at a time. Queued late, a slow Monte Carlo game would hold the iteration's drain; queued all at once, the fleet would repeat step 4's memory level (50 GB) beside the servers and the learner. It is built with Build 2's single queue.
- **Other ratios are not tested now.** No instrument short of an arm resolves the mix. It is routed after the three arms as an arm of its own.
- **The memory read of step 4 was not thrashing.** The kernel's pressure counter showed 57 s of stall in 18 hours of uptime; the swap was compressed RAM holding idle heap.
