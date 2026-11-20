# ADR-0134: M13 Build 2 — one queue of worker slots across harness runs; the same seeds give the same games; the Monte Carlo share rides the queue; the learner's window memory falls fourteenfold; a third server does not help

- **Date:** 2026-11-20
- **Status:** accepted
- **Design-doc anchor:** [m13-plan.md](../design/m13-plan.md), Build 2; anvil-design-v2 §6 (the loop), §9 (the harness); [ADR-0126](ADR-0126-m12-closeout.md) (the next-boundary rows and the infrastructure survey's findings); [ADR-0129](ADR-0129-m13-monte-carlo-opponent.md) (pin 7)

## Context

Build 2 is throughput that changes no game. Before it, a loop iteration ran three harness launches in turn (mirror, each heuristic seat) and a read ran two. Each launch waited for its own last game while the other slots sat idle. Pin 7 adds a fourth and fifth batch to every iteration, the Monte Carlo share, whose games are long and need a larger heap.

Four items were routed here by name: the learner's memory work, the loop config prune, the leak guard on the Monte Carlo path, and a set of small items (a quiet flag for `final_read.py`, a port check before a server starts, the survey's open findings).

## Decision

### 1. One queue of worker slots across runs

**The harness gains `launch-group`.** It takes a spec of several launches and runs them through one set of worker slots. Each member keeps its own run dir, manifest, seed base and store. Members are issued in list order, and a member may carry a cap on its live workers. A pause or a yield in any member applies to the group.

**The loop, both reads and the in-loop arms use it.** The loop's generation is one queue per iteration (`--gen-queue one`, the default; `cells` is the old path). `final_read.py` and `h2h_read.py` run both seat arms in one queue (`--cells` is the old path). The loop's arm reads put the with-lookahead arms first, since their games are longest.

**The proof is a paired cell.** The same seeds went through the old cells and the new queue on heuristic seats with the Monte Carlo share in: 480 of 480 games are identical (`data/runs/b2pair-pair.json`). A game is determined by its member's seed base and its index, and the queue changes neither.

**The wall saving is not calibrated.** The paired cell took about 24 minutes as cells and 21 as a queue, with a forkcheck loading the box beside it. Build 3's arms run at equal box time, so they need no figure.

### 2. The Monte Carlo share

**`--mc-frac 0.1` adds two batches per iteration,** one per seat, played against the Monte Carlo heuristic at the 8-round count budget. They run on a 3 GB heap. They are first in the queue, and each is capped at an eighth of the fleet, so at most a quarter of the workers hold one at once.

**The loop smoke ran it** (`b2loop`: two iterations of 96 games from `iter-405`, the recipe of record, arms every iteration). Each iteration carried 10 Monte Carlo games. The loop completed and its battery reports no anomaly.

### 3. The leak guard on the Monte Carlo path

**The guard is fork commit `68168fb214`** (branch `m13-build2`, on the pin, not pushed). It brackets each Monte Carlo evaluation and compares the live game before and after, as Build 1's guard does for the search. `-Danvil.mc.leakcheck=off` turns it off.

**It is not a boundary, by the empirical proof.** Its forkcheck matches the era's baseline 500 of 500, with copy fidelity at the pin's 467 and 33. The same 96 Monte Carlo games on the pin's jar and on the guard's jar are identical (`data/runs/b2mc-pair.json`).

**It found no leak:** 0 of 1,851 comparisons on each side of the paired cell, 0 of 3,281 in the jar pair, 0 of 754 in the loop smoke.

**The pin has not moved.** Moving it is the user's call. Until then a run that wants the guard passes `--jar data/runs/m13-build2/forge-b2-mcguard.jar`.

### 4. The learner's memory

**The cause was one file read twelve times over.** The loop copies an iteration's whole `mu.jsonl` into each of its batch stores. Every store parsed all of it, in every DataLoader worker. The store now keeps the raw lines of its own games and parses a game when it is asked for.

**A 12-store window falls from 5,958 MB to 425 MB per loader process.** The rows served are identical on two big-run stores.

**At the big run's shape the learner now fits.** A full pass over a 12-store big-run window with 12 loader workers (2,874 trajectories, 684 s) peaked at 21 GB across the learner and its workers, and the box's available memory fell by 19 GB at most (`data/runs/m13-build2/learner-mem2/`). The same shape held about 58 GB before and was killed twice in the big run. Each worker holds a little over 1 GB where it held about 7.

### 5. A third server, with the search off

**It does not help.** 480 network-alone games at 24 workers: 2,053 games an hour on two servers, 1,955 on three, 2,017 on two again (`data/runs/m13-build2/third-server/`). Two servers stay. Serving does not bind with the search off; the workers do.

### 6. Small items

- **A server refuses a port that is already listening** (`check_ports_free`, in the server and in the loop's `_start_server`). gRPC lets two servers share a port, and each then answers part of the run.
- **`final_read.py --quiet`** drops the completion notification. A failed read still notifies.
- **`anvil.runs stop --name N`** stops a run's scope and records `paused`, so `relaunch` resumes it and no alert fires.
- **A memory hold in generation.** The harness starts no new worker while available memory is under 4 GB (`ANVIL_GEN_MEM_FLOOR_GB`) and resumes a gigabyte above it. This is the survey's memory guard for the generation phase.
- **The loop's `--server-args`** passes extra flags to its servers.
- The two stale docstrings the survey named were already corrected.

### 7. Not built, and where each goes

- **The loop config prune is deferred to the recipe rewrite after the arms** (the user agreed, 11-20). `iter-405` carries the plan and schedule heads' parameters and is served with their carries. Removing them changes what is served, so it is a boundary, and Build 2 changes no game.
- **The survey's remaining findings go to the documentation pass that closes M13,** as one infrastructure item: the phone path's file fallback, the multi-row form of the casts, share, entropy and veto guards, the standing watcher's retirement, a pause line recording `done`, the watchdog's kill set chosen by command-line substring, the two remote-control units, the finding-4 leftovers. None of them gates an arm.
- **Straggler carry-over stays where the plan has it,** after the arms. The smoke shows its size at small scale: iteration 1's generation took 1,623 s against iteration 0's 866 s, and one game that ran to the 20-minute draw clock held the queue for most of the difference. At 480 games an iteration one such game is a smaller share.

## Consequences

- **Build 2 is closed. Build 3 is next:** the three arms launch through the queue with `--mc-frac 0.1`.
- **The arms' launch settings change in two places.** The queue is the default. `--rl-workers 12` fits the 64 GB box by section 4's figure, where the recipe of record ran 4; the arms launch with it unless Build 3 finds a reason not to. The learner's load phase was 34% of that pass's wall, so the workers are worth having.
- **What broke.** The queue's spec and record files first sat beside the run dirs and matched a purpose's prefix; the paired cell's driver refused the result at its last step, and the launcher recorded a false failure. They now live under `data/runs/queues/`. I also edited `anvil/runs.py` and the orchestrator while the paired cell was running, against the standing rule; the cell's result was 480 of 480 and it was not rerun.
- **No standing rule is born.** The port check turns the one-server-per-port rule into code.

## Addendum (2026-11-20, afternoon): the guard is the pin; the watchdog's classes are right

- **The fork pin is `68168fb214`,** on the user's word, pushed to the fork's `master`. It is not a boundary (section 3). The serving jar is `data/runs/m13-build2/forge-b2-mcguard.jar`, the same file as the fork's built jar.
- **The devlog's note that the memory watchdog misses the learner's loader workers was a misreading.** The workers carry the learner's command line and are counted in the `rl` class: 14 processes and 21 GB at the full-window pass's peak. The `rl_worker` class holds the forkserver alone. The watchdog's kill set takes both classes and their descendants, so its coverage is whole. Nothing is changed.
- Build 2's branch is merged to `main`.
