# ADR-0115: M12 Build 4½ — the shakedown scoped: four arms at equal box time through `selfplay.py`

- **Date:** 2026-09-21
- **Status:** accepted (user, 09-21: the shakedown launches first, the documentation pass runs beside it); the census jar `cbe386d2c6` proven 11:53 (499/500), the shallow-wide rate measured 12:03 (587 g/h peak); the contention smoke clean (below)
- **Design-doc anchor:** §6 (training pipeline), §9 (engine & infrastructure); m12-plan Build order 4½ / 4¾

## Context

Build 4 closed with the launch condition cleared ([ADR-0112](ADR-0112-m12-build4-allocation-head-served.md):
act − on +2.29 ± 1.02 at 2,000 games per arm), the loop wired to run the search as its behavior policy
([ADR-0113](ADR-0113-m12-loop-wiring.md)), and route (b) closed on the number
([ADR-0114](ADR-0114-m12-route-b-rescoped-void-rescue.md)). What is not measured is the one thing the big run
commits four to six weeks to: **which search shape turns box time into network-alone strength fastest**
([ADR-0106](ADR-0106-m12-evening5-surface-acting-and-search-shape-reads.md) decision 2 — the training-signal
curve, read by a multi-arm shakedown at equal box time; [ADR-0109](ADR-0109-prelaunch-completeness-audit.md)
adds the allocation arm). The per-copy prices are known: the recipe 347 g/h on the merged jar (24 × 2, the
median of three cells), the deep round ×2.83 box time per game (ADR-0106 C3), the allocation head ×1.6 games
in search cost at 51% of windows searched (ADR-0112). The shallow-wide shape's rate is measured by the
09-21 bench cell (`data/runs/build4-prep/bench-shallow.md`).

The 09-21 review (this session) also settled the order: the shakedown launches first and the documentation
pass (Build order 4¾) runs while its arms fly — the pass needs no box, the shakedown needs no docs, and the
plan as written already expected the shakedown's verdict in the docs. Before the launch, the small
resilience items landed the same day (ADR-0107 addendum 09-21: `pause` / `relaunch`, the sweep's
auto-resume, the heartbeat, the headless fallback, `--wall-hours`) and the fork's census bundle
(`cbe386d2c6`, forkcheck `run-20260921-build4-census`).

## Decision

1. **Four arms, one box, sequential, each a `selfplay.py` loop from the same day-zero build**
   (`data/training/m12-build4-e1a/last.pt`; ADR-0112's served build of record) on the same pinned jar
   (the census tip `cbe386d2c6` once its forkcheck passes; the recipe is byte-identical to the read jar's
   game path), the same loop settings as the run of record (`d6-run11`: 480 games per iteration, lr 1e-5,
   replay 4 at weight 0.33, KL guard 0.06, the ADR-0113 search terms at their smoke shares), 24 workers × 2
   servers, drills OFF (the M4 drill phase would confound the arm comparison; drill-finding is the
   search's own job under ADR-0101 item 7 — the certifier merge lands during the shakedown for the big
   run's jar), no day-zero paired read per arm (ADR-0112's b4post read is the day zero of record):

   | arm | AnvilRun recipe | `--search-alloc` | price (per game vs the recipe) |
   |---|---|---|---|
   | `recipe` | `-search -searchrate 1 -searchrolls 2 -searchsurf 2 -searchsurfcap 8 -searchact 0.10 -searchtemp 0.025 -searchactkinds entity_one,entity_set,mode` | off | 1.0 (347 g/h) |
   | `alloc` | the recipe | head (tau from the ckpt's fit record, floor 0.1; re-derived per cycle) | ≈ 0.6 search cost, wall −40% (ADR-0112) |
   | `shallow` | `-search -searchrate 1 -searchrolls 1 -searchact 0.10 -searchtemp 0.025` | off | **587 g/h peak / 478 wall** (the 09-21 cell, 24 × 2, 64 games, 0 crashes: ≈ 1.7× the recipe's rate → ≈ 15–17K games in 30 h) |
   | `deep` | the recipe + `-searchdeep 3 -searchdeepleaf h2 -searchdeeprolls 4 -searchdeeplo 0.02 -searchdeepfloor 0.1 -searchclock 3600` (the priced bench arm) | off | ×2.83 box time (≈ 35% of the recipe's games) |

2. **Equal box time by the driver's `--wall-hours`** (the 09-21 addition: accumulated across pauses):
   **W = 30 h per arm** of generation + training, which the recipe converts to ≈ 10K games (21 iterations),
   the deep arm to ≈ 3.5K, the shallow arm to more, the alloc arm to ≈ 14K. The four arms ≈ 5 days plus
   the closing reads ≈ 1 day → the week ADR-0106 sized. **Arm order: recipe → alloc → shallow → deep** (the
   product first: if the loop under the recipe breaks, the rest is moot; the deep arm last because it is
   the one most likely to be dropped on price).

3. **Each arm closes with** (a) the 2,000-game read vs the heuristic on the fixed population
   (`final_read.py`, 1,000 per seat, network alone, the fleet pinned 24 × 2) — the PRIMARY number, read
   as the gain over the day-zero 0.5265 ± 0.0112; (b) the last mid-run lookahead arm (`--arms-every 5`,
   `--arms-lookahead on`, 200 games) as the network-alone vs with-lookahead gap; (c) the state-ranking
   Spearman on the frozen holdout from the Build 1 cells where a checkpoint-eval path exists (else
   routed to the big run's mid-run health).

4. **Pre-registered verdict (ADR-0106, restated):** the big run takes the arm with the best network-alone
   gain per box-hour; ties within one SE go to the cheaper arm; "no detectable difference" at this size is
   itself the decision — the cheap arm. Power: ±1.1pp per read, so a 1pp difference is inside noise by
   construction; the arms are the last landmine catcher first and a shape read second.

5. **After the verdict:** the settings pass on the winner (lr / KL / replay under the dense mix; the
   surface round's breadth as an axis — ADR-0109), the learning-curve slope re-issued from the winner's
   curve for the power statement, then the big run's launch ADR (the pacman pin that day, the certifier
   merge on the jar, the kernel updates deferred).

6. **Run hygiene:** one chain through `anvil.runs launch` with `--resume-on-gone` and `--watch` on the
   arm roots; each arm's loop is pausable (`anvil.runs pause`) for a maintenance reboot and resumes its
   own state; the GPU yield and the VRAM park heartbeat; the chain's `read.md` accumulates the per-arm
   numbers as they land.

**The contention smoke (12:03–12:09):** a synthetic foreign GPU job (`scripts/gpu_burner.py` under `setsid`:
4.9 GB resident, 88% SM for 360 s) beside a 4-game recipe smoke at 4 × 1 — the yield fired on it
(`gpu-yield.json`: "python3 4968 MB sm 88%"), the in-flight games finished 4/4 won, **0 deadline or poison
lines** at the 20 s bridge deadline; per-game wall median 86 s vs 32 s on the same jar and recipe without
the job (max 326 vs 60 s). Ordinary desktop and ComfyUI use costs the run wall, nothing else; a foreign
job that saturates the card slows in-flight games ≈ 2.7× and gates new chunks until it leaves.

**Amended 2026-09-21 20:37 (ADR-0116):** the day-zero build is the refit build `m12-build4-e1a-tgt` (the
corrected target head; the policy otherwise byte-identical to e1a); the chain gained a step 0 — the
day-zero build's own 2,000-game read, the reference for every arm's gain (the old 0.5265 was the legacy
head's). The first launch (13:00, from e1a) was paused at iteration 3 on ADR-0116 and its artifacts
deleted; relaunched 20:37 from the refit build, the same four arms and 30 h each.

## Consequences

- Build order 4½ amended to this ADR (four arms, `--wall-hours`, the arm order, drills off); 4¾
  amended: the documentation pass runs BESIDE the shakedown, its scope unchanged.
- The certifier merge (routed to "Build 4½ or the closeout") is scheduled: during the shakedown week, on
  the fork, for the big run's jar (the big run mines drills from network-played games and re-certifies
  the existing drills on the new pin — both triggers fire at its launch).
- Standing rule (born here → standing-rules.md, search / budgets / run sizing): **an arm's box time is
  the driver's accumulated wall (`--wall-hours`), never its game count; a paused arm resumes its budget.**
- Routed by name: the state-ranking Spearman checkpoint-eval path (if absent when the first arm closes);
  the shakedown's own `read.md` → the big run's launch ADR.

## Addendum 2026-09-22 — the shakedown's checkpoints are kept; the big run continues from the winner (user)

The big run **continues from the winning arm's final checkpoint**: the settings pass runs a few iterations
per setting from that state, the best setting resumes from there (the loop state carried when it fits,
else a warm start from the weights alone). Thirty hours of learning under the recipe of record are not
discarded for a day-zero origin; the power statement's slope is re-issued from the big run's own curve
at 50K games regardless. The losing arms' final checkpoints and their 2,000-game reads are kept as the
era's ladder (the shape comparison in checkpoint form) and their stores as baseline-era arm stores.
**Promotion follows the standing gate, not the run's purpose**: any shakedown checkpoint that clears
+2.5pp over the era reference at 2,000 games is the RL checkpoint of record the day it reads. The one
case for a day-zero restart — a settings pass that changes the learner materially — still warm-starts
from the winner's weights.
