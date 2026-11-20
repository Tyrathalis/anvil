# M13 plan — WHAT IN THE RECIPE PRODUCES THE GAIN (OPENED 2026-11-18, ADR-0127)

**Doc status:** living · M13 plan (opened 2026-11-18, ADR-0127): three arms at equal box time after an upstream merge; the merge and the era bridge closed 11-18 (ADR-0128; the kill condition not tripped), Build 0 steps 3 and 4 closed 11-19 (ADR-0129: Monte Carlo at 8 rounds, +9.32 ± 0.77pp over the plain heuristic; iter-405 level with it at 0.5099 ± 0.0071), pin 7 set at 10% Monte Carlo in every arm, step 5 closed 11-19 (ADR-0130: iter-405 on held-out precons 0.4078 ± 0.0069 with card text, 0.2798 as served), pin 6's deck list and eras set, step 6 closed 11-19 (ADR-0131: the copier fails on objects of a player who has left the game), Build 1's inert commit built and proven 11-20 (ADR-0132: forced-decision replay; forkcheck 500 of 500), its fixes commit landed 11-20 on the user's call (ADR-0133: a search copy could leak mana into the live game; a boundary for searched games; pin cf78d3f046), Build 2 closed 11-20 (ADR-0134: one queue of worker slots across runs, 480 of 480 paired games identical; the Monte Carlo share in the queue; the learner's window memory down fourteenfold; a third server does not help; the config prune deferred to the recipe rewrite), Build 3 open 11-20 (ADR-0135: the arms' launch settings and pre-registered reads, the soft-target term built, the control arm launched; the soft definition and its dose ladder wait on the user); the record: m13-running-record.md

*Status: OPEN. Chartered 2026-11-18 ([ADR-0127](../decisions/ADR-0127-m13-charter.md)) from [ADR-0126](../decisions/ADR-0126-m12-closeout.md)'s routing table, re-read against the pre-scoping measurements ([m13-prescoping-measurements.md](m13-prescoping-measurements.md)). The user agreed the order and pinned the seven forks the same day. The session-by-session record is [m13-running-record.md](m13-running-record.md). Build 0 step 1, the merge, landed 11-18 ([ADR-0128](../decisions/ADR-0128-m13-upstream-merge-20261118.md)); step 2, the era bridge, closed 11-18 with its kill condition not tripped (`iter-405` 0.6064 ± 0.0069 on the merged jar, −1.53 ± 0.75pp paired against the old jar); step 3 closed 11-19 ([ADR-0129](../decisions/ADR-0129-m13-monte-carlo-opponent.md): the count budget calibrated at 8 rounds, the Monte Carlo seat +9.32 ± 0.77pp over the plain heuristic at about ten times the cost per game); step 4 closed 11-19 (`iter-405` reads 0.5099 ± 0.0071 against it, −9.12 ± 0.78pp paired against its plain-heuristic arm; a game costs 4.2 times a plain one); pin 7 is set (11-19: Monte Carlo at 10% of games in every arm); step 5 is next.*

## Charter

**M13 finds what in the recipe of record produces its gain, by training three arms from one checkpoint at equal box time and reading each head to head against the control.** The big run showed that training scale works (+9.46pp over its era reference, network alone). It did not show whether the search teaches, and its last segment did not improve the network. The milestone's product is a recipe of record with a measured reason for each part it keeps.

The deployable asset is still the network alone. The benchmark it is building toward is Commander precons, two-player first.

## The facts it starts from

- **Segment 5 failed to improve the network.** `iter-405` and `iter-513` are level head to head (0.5019 ± 0.0055), under a halved anchor draw. A control arm is expected to move little, so a real gain in another arm is easy to see.
- **The search's ranking carries signal where it does not act.** The un-acted slope is +0.351 ± 0.073 on 2,264 windows. The soft-target arm cleared its gate with no dose note.
- **Where the search acts, its preference was not realized.** The acted slope is −0.061 ± 0.110 on 163 windows, 1.9 standard errors from the 09-15 figure. It is a flag, not a finding. The search-off arm tests it.
- **The search costs 5.2 times the worker time of a game.** A search-off arm plays about 3.5 times the games at equal box time (*estimate*). With the search off, serving is the bottleneck (servers 89% busy).
- **Generation waits on its tails.** The big run's slots were idle 32% and 47% of its generation cells' wall time. Each iteration drained three cells.
- **The head-to-head read resolves 0.55pp at 5,000 games**, against 0.73pp through the heuristic. A week-long arm moved about 1.5pp at the big run's slope.
- **Four-player costs 13 times two-player**, and 15% of rollouts through the game copier fail on upstream master. The cause is not identified.
- **Upstream is 1,340 commits ahead.** Its heuristic has a Monte Carlo mode; the count-budget patch that makes it reproducible is built and unpushed ([m13-upstream-merge-scoping.md](m13-upstream-merge-scoping.md)).

## Build order

### Build 0 — the upstream merge and its reads

The merge is the opening boundary. It lands alone, as one commit after a tag, so that a changed number has one cause.

1. The merge, the forkcheck on the merged jar (for crashes and the copy-fidelity rate, not identity), and the count budget on the jar.
2. **The era bridge:** `iter-405` and `d6-run11/iter-019` against the plain heuristic, paired on the 11-07 confirm's seeds. This is M13's day-zero.
3. Monte Carlo on against off, heuristic seats only, and the count budget's calibration to an idle desktop.
4. `iter-405` against the Monte Carlo opponent. This read decides whether Monte Carlo becomes a training opponent (ADR-0126, 11-17 addendum).
5. **The held-out precon read:** `iter-405` on precon decks, two-player, with the share of unseen cards per deck on file. **Closed 11-19 ([ADR-0130](../decisions/ADR-0130-m13-held-out-precon-read.md)):** 0.4078 ± 0.0069 against the plain heuristic with unseen cards' text in the table, 0.2798 ± 0.0063 as served; the median deck is 80% unseen.
6. The copier's cause, on the merged engine. No four-player search or Monte Carlo read runs before it. **Closed 11-19 ([ADR-0131](../decisions/ADR-0131-m13-copier-cause.md)):** a player who has left the game; survivors still refer to that player's commander and effect cards. The two skips are routed to Build 1.

### Build 1 — the second fork commit: replay and the routed boundary items

One commit after the merge is proven. Each part is inert on the game path, so the commit is offered under ADR-0025's exemption and proven by trace hashes. A mismatch makes it a boundary.

- **Forced-decision replay** (the user, 11-18). A replay mode feeds a stored game's recorded answers back in place of a server. Its fidelity read: about 20 stored model-served games replayed, winners and final states compared with `games.jsonl`. If it holds, every stored window is reachable again: the gate on stored games, ADR-0125's truth stream on stored states, and crash reproduction.
- **The starting player in every game record.**
- **The next-boundary items of ADR-0126:** the `CensusRun -certify` and `PayDirective` deletion with the `payment-evalset-v2` re-certification, the NullPointerException crash, the oversize game's source, a heap flag for reads with deep rollouts.
- A crash fix never qualifies for the exemption. If the NullPointerException fix changes a game, it moves into the merge's boundary and Build 0's reads run after it.

**Built 11-20 ([ADR-0132](../decisions/ADR-0132-m13-build1-forced-decision-replay.md)), as two commits.** The inert one (fork branch `m13-build1`) holds the replay, the starting player, the deletion, the frame cap fix and a copy-leak guard, and matches the era's forkcheck baseline 500 of 500. The fidelity read is on file: 389 of 420 games replay identically, 26 more agree at every served decision, 5 differ. The re-certification retired `payment-evalset-v2` (25 of 280 windows reached). The fixes one (branch `m13-build1-fixes2`) holds two crash fixes, ADR-0131's skips and the fix for a leak the replay found: a search copy can put mana into the live game ([ADR-0133](../decisions/ADR-0133-m13-search-copies-leak.md)). It changes searched games; the user landed it 11-20 and the pin is `cf78d3f046`. The heap flag is `final_read.py --heap`. The token mapping failure is not fixed.

### Build 2 — throughput that changes no game

- **One queue per iteration** in place of three cells, in the loop. It leaves one drain per iteration where there were three.
- **One queue across seat arms** in `final_read.py` and the head-to-head read.
- **The learner's memory work and the loop config prune** (ADR-0126's next-boundary rows), since the loop is open anyway.
- A third server, tried with the search off, where serving binds.
- **The Monte Carlo share in the queue** (pin 7). Every iteration carries its 10%, as whole worker slices with the larger heap cap. Within an iteration those slices are queued early and interleaved, a few at a time, so their long games overlap the rest of the queue and no more than a quarter of the fleet holds one at once.

Proven by a paired cell: the same seeds through the old cells and the new queue give the same games.

**Built 11-20 ([ADR-0134](../decisions/ADR-0134-m13-build2-one-queue.md)).** The harness's `launch-group` runs several launches through one set of worker slots; the loop, its arm reads, `final_read.py` and `h2h_read.py` use it. The paired cell: 480 of 480 games identical. The Monte Carlo share is `--mc-frac 0.1`, two capped batches at the head of the queue. The store holds an iteration's mu and search rows as raw lines of its own games, and a 12-store window falls from 5,958 MB to 425 MB per loader process. A third server with the search off does not help (2,053 and 2,017 games an hour on two, 1,955 on three). The Monte Carlo leak guard is fork commit `68168fb214`, proven not a boundary; the user made it the pin 11-20. **Not built:** the loop config prune, which removes served parameters and so is a boundary; it goes to the recipe rewrite after the arms.

### Build 3 — the three arms

All three start from `iter-405` on the merged jar, run for equal box time under `--wall-hours`, and keep 480 games per iteration.

| Arm | What changes | What it answers |
|---|---|---|
| **Control** | Nothing: the recipe of record | The reference. Whether the recipe still improves the network on the new engine |
| **Search off** | No search in generation, so no acting by it and no labels from it | Whether the search teaches at all. It gets about 3.5 times the iterations and training steps |
| **Soft targets** | The search's ranking becomes a training target at windows where it does not act | Whether the ranking teaches more than the acted line does |

- **Order:** control, then search off, then soft targets. The control runs first because both reads need it.
- **The search-off arm confounds "no search" with "more updates"** (the user, 11-18: same game count first). If it wins, a follow-up arm holds the updates equal and gives each more games.
- **The reads.** Each arm's final checkpoint against the control's, head to head on 5,000 fresh-seed games. The read against the plain heuristic is the continuity number. The in-loop arm reads continue.
- **The soft-target arm's known risk** is ADR-0111: offline distillation toward the search lost up to 47pp with the dose. Its target weight is pinned from a short dose ladder before the arm launches.

### Build 4 — the value-head track, beside the arms

[ADR-0125](../decisions/ADR-0125-value-head-track.md) in a worktree: the truth stream, the critic, the student. It opens with the recompute of the Build 1 holdout figure with ties averaged, since the guard floors are in the old unit. Its bars are pinned at its own scoping. It does not enter an arm.

### After the arms

- **Straggler carry-over** (pin 3). With one queue, an iteration still drains once: about 15 of generation's 83 minutes per iteration in the big run (*estimate from the cells' idle totals*). Carry-over removes that, and it is what makes a cap raise safe. It changes which checkpoint finishes a game, so it gets its own paired comparison against the winning recipe. It is designed at the desk while the arms run.
- **The cap raise**, priced after carry-over.
- **The recipe of record is rewritten** from the arms' reads, and the pool grows by precon era on it.

## Pins (the user, 2026-11-18)

1. **Arm length:** a week each. The search-off arm's in-loop reads are watched for an early, clear separation.
2. **The arms' bar:** an arm differs from the control at 2 standard errors head to head on 5,000 games (1.1pp). An arm inside that band is reported as level, with the power statement beside it.
3. **Straggler carry-over runs after the arms.** Every arm goes without it, so the comparison is fair; each arm gives up about 15% of its games (*estimate*).
4. **The play-or-draw surface lands after the arms**, with the first pool-growth boundary, so the arms run on one engine.
5. **`Hard.ai` and `Hardest.ai` stay out of the arms' profile draw.** They are read once in Build 0 against the four current profiles.
6. **The benchmark's pins** *(set 11-19, [ADR-0130](../decisions/ADR-0130-m13-held-out-precon-read.md) addenda: 178 decks; three eras, 2011 to 2020, 2021 to 2023, 2024 to 2026, grown oldest-first; the rules and the reference opponents are open)* (era boundaries, the rule set and bans per track, the reference opponents) are set when the held-out precon read is in.
7. **Monte Carlo is a training opponent at 10% of games, in every arm** (the user, 11-19, on Build 0's read 4; [ADR-0129](../decisions/ADR-0129-m13-monte-carlo-opponent.md), second addendum). The share comes out of the heuristic-seat games: about 50% self-play, 40% plain heuristic, 10% Monte Carlo at the 8-round count budget. Other ratios are an arm of their own after the three.
8. **The search-off arm keeps 480 games per iteration.** An equal-updates arm follows if it wins.
9. **Forced-decision replay is an M13 item** (Build 1).

## Done-when

1. The merge is landed and the era bridge is on file.
2. Forced-decision replay has its fidelity read on file, pass or fail.
3. The single queue runs in the loop and its paired cell matches.
4. Each of the three arms is read head to head against the control on its bar.
5. A recipe of record is named with the reason for each part, or the ADR says which parts the arms could not separate.
6. The held-out precon read and the copier's cause are on file.
7. The value-head track's first layer is read on its bar.
8. The closeout routes the deferred items by name.

## Kill conditions (pre-registered)

- **The era bridge.** `iter-405` reads more than 3pp below its paired old-jar figure against the plain heuristic. The arms do not start; the difference is attributed first (the heuristic's change against a broken hook).
- **An arm trips a run guard twice** on the same row. The arm stops and is read where it stands.
- **The control arm falls.** Its in-loop read drops more than 2 standard errors below day-zero at the mid-point. The recipe does not hold on the new engine; the arms pause and the value anchor's draw is read first.
- **The soft-target dose ladder loses at every dose.** The arm is not run, with the ladder as the reason.

## Inherited obligations and hazards

- Power statement before every launch. Arms are sized against the read's resolution before they are ordered.
- Numbers are not compared across the merge. The era bridge is the only link.
- A fixed truth set is memorized inside a run and goes stale as the policy moves (ADR-0124).
- No tree edits while an arm runs; desk work is in worktrees.
- Calibrated timings launch with `--quiet-box`.
- The upstream stream is unchanged: one engine PR and one GUI PR at a time, from `../forge-upstream`.

## Out of scope / routed by name

| Item | Disposition |
|---|---|
| The opponent mix (for example 60 / 30 / 10 against the arms' 50 / 40 / 10) | After the arms, as its own arm against the winning recipe: the search decision changes what each kind of game costs |
| More learning per game | Folded into the search-off arm and its follow-up; a separate arm only if those leave it open |
| The engine benchmark and port | Deferred behind the search-off read: search off (about 5 times) and the queue are cheaper throughput |
| The short format, the Pauper testbed, a second format | Deferred: the benchmark is precons |
| The belief sampler, ponder-time search | After the arms' decision on search |
| A hidden-card prediction target (the opponent's deck contents from the commander and the cards seen, labelled by full-visibility states) | With Tutor: it shares the deck representation. Raised 11-18; read as intermediate data whether or not it moves the winrate. Distinct from the belief sampler above, which it could later feed |
| The same target for the model's own deck (the user, 11-20): predict its own library's contents from the cards seen. It covers a card exiled face-down at random, and playing a deck whose list the model was not given | With the hidden-card target above: one head, both players. Whether the own-deck list is withheld from the observation is a separate surface decision, made there |
| The four-player track | After the copier's cause and the two-player held-out read; a held-out pod read before any pod training. It opens by re-measuring the rollout failure rate with ADR-0131's skips in the pin (not yet run) |
| Pool growth by precon era, the trunk-capacity probe | After the recipe is rewritten; the probe before any capacity change |
| Learnable stops | Re-deferred: a new surface, after the arms |
| The generic target choosers, the untraced callbacks, the late-payability scan | With the play-or-draw boundary |
| Shipping the network | The user's call on timing; independent of this order |
| The infrastructure survey's remaining findings (ADR-0126, first addendum; the list is in ADR-0134, section 7) | The documentation pass that closes M13. Build 2 built the stop verb, the generation memory hold and the port check |
| The loop config prune (the plan and schedule heads' parameters in the checkpoint) | With the recipe rewrite after the arms: it changes what is served (ADR-0134) |
| The replay's fork point (stop at a tape entry, then the existing copy runners) | With its first consumer, Build 4's truth stream |
| The record of a one-candidate `chooseSingleStaticAbility` ask (the oversize game's size) | With the play-or-draw boundary: it changes the history the server is shown |
| The single-occurrence crashes (`getDividedValue`, `AttachAi.affectsAttached`, `checkRemoveCounterCost`, the `StackOverflowError`), the copier's mana copy, the `OptionalDecider` ordering, the `SacrificeEffect` index, the charm null check | The upstream worklist, as candidates |
| A Spellbench entry, an LLM opponent seat, the learned ability encoding, learned dynamics, the skill token, match play, Tutor and Mentor, Trackio | Re-deferred with ADR-0126's reasons |
