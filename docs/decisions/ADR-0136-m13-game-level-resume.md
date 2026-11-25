# ADR-0136: The loop resumes an interrupted generation at the game

- **Date:** 2026-11-21
- **Status:** proposed — built and unit-tested on branch `m13-game-resume`; not landed. It lands at an arm boundary after the paired proof in section 4.
- **Design-doc anchor:** anvil-design-v2 §6 (the loop), §9 (harnesses stop gracefully and resume at seeded game granularity); [m13-plan.md](../design/m13-plan.md), pin 3 (straggler carry-over); [ADR-0134](ADR-0134-m13-build2-one-queue.md); [ADR-0107](ADR-0107-run-launcher-and-checkin.md)

## Context

**The loop did not resume at the game; it resumed at the batch.** On 11-21 the control arm was paused 122 games into iteration 17 for a reboot. The relaunch opened new run dirs and played all 480 games again. The loop reused a batch only when its store existed, and a batch has no store until every game is in.

**The harness already keeps the ledger.** Each worker invocation appends a finished game to its own `games.jsonl`, and `harness resume` issues only the games that are missing, for a whole queue. The loop never called it.

**A second fault sat beside the first.** A STOP that reaches a harness dir mid-generation (`anvil.runs pause --scope all`) makes the harness drain and exit with status 0. The loop then ingested the short batches and trained on them.

## Decision

### 1. An interrupted generation is resumed, not restarted

At an iteration's start the loop looks for the unfinished run dir of each batch that has no store. It resumes them when they would play exactly what a fresh launch would: the same games, start index and seed base, and one queue whose record is intact. Otherwise it launches fresh, as before.

Finished games are kept. Games in flight at the stop are played again from their seeds, because a game's process does not survive the stop. That is at most one game per worker slot.

### 2. The unfinished games' records are dropped before the resume

A replayed game under search need not repeat its first attempt (serving numerics move the acting rule at temperature 0.025). Its first attempt's rows must not be joined to its second attempt's frame. Before the server restarts, the loop drops:

- from the iteration's `mu.jsonl`, the rows of games no invocation finished;
- from each invocation's `labels.jsonl`, the rows of games that invocation did not itself finish.

Without this, ingest would see conflicting behavior-policy records, drop the game's records whole, and the learner would skip it.

**An uninterrupted iteration runs none of this code path's writes.** The purge and the resume run only when an unfinished run dir is found.

### 3. Box time is charged for the work that is kept

- **A loop that was killed** (a reboot, `pause --now`) never saved its clock. The loop now records each generation segment's start. On resume it charges the wall budget from that start to the last game any member finished.
- **A generation that stops short** (a graceful STOP in the harness dirs) raises in the loop. The loop saves its clock, ingests nothing, trains nothing and exits as paused. The relaunch resumes the iteration.

Yielded seconds inside a killed segment are not subtracted. The arms run with no yield.

### 4. The proof owed before it lands

It is not run now: a box job beside the control arm would tax that arm alone (ADR-0135, section 3). At the control's stop, before the search-off arm:

1. **Network alone, exact.** One 96-game iteration from `iter-405` with the search off, uninterrupted; the same seeds again with `pause --now --scope all` mid-generation and a relaunch. Registered: every game's trajectory identical, 96 of 96, and the stored mu rows identical.
2. **Under search.** The same pair with the recipe. Registered: every game finished before the stop identical; ingest reports no conflicting mu attempt; the search join matches every row. Replayed games that differ are counted and reported, not failed.
3. **The graceful stop.** `pause --scope all` without `--now`: the loop exits as paused, no store is written, and the relaunch completes the iteration.
4. **The clock.** The resumed loop's wall figure equals the uninterrupted one's to within the two server starts.

If cell 1 is not 96 of 96 the change does not land.

### 5. Straggler carry-over builds on the same ledger, after the arms

Carry-over (pin 3) lets a game outlive its iteration; resume lets an iteration outlive its process. Both read one per-game ledger in place of a batch's done-or-not. Carry-over changes which checkpoint finishes a game, so it changes the data and stays after the arms. Resume changes no finished game and can land between them.

## Consequences

- **A pause at any point costs the games in flight,** not the iteration. `pause --scope all` becomes safe on a loop.
- **The comparison between arms is unaffected** if the proof holds: the path runs only after an interruption, and its box time is charged.
- **Not covered:** a stop during training or an in-loop read still restarts that step. Training is 4 to 7 minutes; a read is one queue and could use the same resume.
- **Routed:** the quickstart's pause section, when this lands. The cells path (`--gen-queue cells`) resumes a single unfinished batch through the same code and is not in the proof.
- **No standing rule is born.**

## Addendum (2026-11-21, later): the in-loop read resumes too; training does not; the landing waits for the arm's end

- **An interrupted in-loop read was lost, not restarted.** The loop writes the next iteration into its state before the read begins, so a relaunch went straight on and that read was never made. The "Not covered" line above had this wrong.
- **The read now resumes at the game** (branch `m13-game-resume`). A mark in the iteration's dir says the read is owed. A relaunch finishes it before the next iteration, through the same queue resume. Its killed segment is charged to the wall budget. A read that stops short writes no report and the loop exits as paused.
- **The proof gains a cell.** 5. One in-loop read, network alone and with lookahead, killed mid-read and relaunched, against the same read uninterrupted. Registered: the network-alone arm's games identical; the report is written once.
- **Training does not resume mid-step, by decision** (the user agreed). An exact resume needs the optimizer, the loader's place in its schedule, the auxiliary weights' calibration, the anchor's draw count and the generators restored, and GPU arithmetic gives no bitwise check that they were. The gain is 4 to 7 minutes an interruption. A stopped training step restarts from its start, as now.
- **The landing waits for the control's end** (the user, 11-21): one loop version per arm. Reboots this week pause at an iteration boundary with the default `anvil.runs pause --name m13-control --wait`.
