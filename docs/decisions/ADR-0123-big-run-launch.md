# ADR-0123: The big run's launch — warm start, recipe of record, weekly segments, the bar and the kill rules

- **Date:** 2026-10-05
- **Status:** accepted (the launch itself follows the chain script, the one prerequisite named under Consequences)
- **Design-doc anchor:** §3e (search as the behavior policy), §4 (value head), §6 (training pipeline); m12-plan Build order 5 (the big run) and 6 (the close); ADR-0115 (the shakedown's verdict), ADR-0118 / ADR-0119 (the value-head recipe), ADR-0122 (the served decoder)

## Context

Every read the launch was waiting on has closed, each on its pre-registered bar:

- **The search recipe** is the shakedown's alloc arm ([ADR-0115](ADR-0115-m12-shakedown-scoping.md) verdict 09-27): the best network-alone gain per box-hour; no arm cleared promotion.
- **The value-head recipe** is rung 2 of the [ADR-0119](ADR-0119-value-function-first-before-the-big-run.md) ladder (closed 10-03): the head-only anchor at weight 0.1, the value gradient stopped at the trunk, the trunk at lr 3e-6 and the detached head at 1e-4. Its Spearman clause cleared (0.39 → 0.45 plateau, every row above day-zero's 0.374) and its margin read cleared (−0.47 ± 0.69pp vs alloc on 4,920 paired games, above the fixed −1.0pp margin). The trunk lr is part of the recipe: without it the policy ran away (the 10-01 kl halt).
- **The warm start.** The drifted-trunk recovery read (10-04, `settings-pass5`) started the rung-2 recipe from `shakedown-alloc/iter-019` (Spearman 0.250) and climbed every iteration to 0.439 ± 0.023 at iteration 6 (bar ≥ 0.350); the 2,000-game read on `iter-006` was 0.5285 ± 0.0112, inside the flag. The no-anchor control (10-04, `settings-pass6`) ran the same flags minus `--value-anchor` from the same start and stayed flat at 0.245–0.261: the anchor term earns its place and the slow trunk alone does not hold the ranking.
- **The jar and the decoder.** Fork `5bd040351f` (`forge-tgtmask3.jar`, forkcheck PASS 10-05 00:15) carries the cast-mask fix, the shuffle mark and the union target mask ([ADR-0122](ADR-0122-union-target-mask.md)); the mask's agreement check cleared (0 / 23,647 targets outside) and its paired read cleared (−0.61 ± 0.49pp, `no_shape_fit` vetoes −38%, wall 42.3 min). The decoder serves masked.
- **The resolution of record is raw.** The Ante re-measure (10-03) came in at ×1.03–1.04 effective samples against the 1.5× bar, so the amortized advantage head is routed, not built, and this ADR quotes raw power.
- **The reference re-read under the mask.** `d6-run11/iter-019` on the launch jar with the decoder masked: **0.534 ± 0.011** at 2,000 games (`tgtmask-paired2`, 10-04), the same number as the unmasked 0.5348 ± 0.0110 of record.

What this ADR has to pin is everything the chain reads from: the start point, the exact flags, the run's shape and length, the reads at each review point, the bar, and the numeric form of the two Build 5 kill rules.

## Decision

### 1. Two different `iter-019`s, kept apart

| Role | Checkpoint | Read |
|---|---|---|
| **Era reference** (the promotion bar's base) | `d6-run11/iter-019` | 0.534 ± 0.011 masked on the launch jar (10-04); 0.5348 ± 0.0110 unmasked of record |
| **Warm start** (the kill rule's "flat" base) | `shakedown-alloc/iter-019` | 0.5394 ± 0.0070 fresh unmasked (10-01); **not yet read masked** |

The run warm-starts from the weights of `shakedown-alloc/iter-019` (ADR-0115: the winner's weights, never a day-zero origin). `settings-recovery/iter-006` was considered and not taken: it is a nine-hour read, not a run, and the kill rule's base is the checkpoint with the fresh read. The chain's **first step** reads the warm start on the launch jar with the decoder masked, network-alone at 2,000 games and with-lookahead at 1,000, so every mid-run comparison is same-jar and same-serve.

### 2. The recipe of record

One loop, `anvil.training.selfplay`, at 24 workers × 2 servers on `forge-tgtmask3.jar`, served build `m12-build4-e1a-tgt` with table `abil-cf2ca6ba-b4s-qwen3`, pool `cf2ca6ba`:

```
--games 480 --games-per-pair 2 --workers 24 --chunk 30 --seed-base 20260921
--ent-weight 0.003 --ent-floor 0.08 --rl-seg 128 --guard-kl 0.06 --guard-ent-mult 2.0 --guard-veto-mult 1.5
--guard-casts-floor 0.8 --penalty 0.02 --heur-frac 0.5 --value-weight 0.5 --traj-per-step 4
--reask --search-recipe "$RECIPE" --search-alloc head --search-floor 0.1
--distill-carry-w --alloc-carry-w --state-bank data/runs/m12-build1
--value-anchor data/runs/m12-build1 --anchor-weight 0.1 --value-stopgrad-trunk --trunk-lr 3e-6 --value-head-lr 1e-4
--grad-norm-every 50 --arms-every 5 --arms-lookahead on --arms-games 200
--guard-spearman-floor 0.15   (segment 1) / 0.30 (segments 2–6)
--iterations 2000 --wall-hours 168 × segment
```

`$RECIPE` is `scripts/recipe.sh`'s RECIPE string (the shakedown's recipe + alloc arms). `scripts/big_run_chain.sh` is the single source of this flag set from the day it lands; the quickstart points at it. Drills stay off: nothing has run with them under this recipe, and the plan's item 7 makes the search the run's own drill-finder. The trunk lr stands as written: the attribution replays showed 3e-6 restores the control's policy step (kl_mu 0.0020 vs 0.0024), so the step is matched to alloc's, not a third of it, and the margin read's −0.47pp is inside noise. A six-week run is not where an untested schedule goes.

The Spearman guard floor is 0.15 for the first segment because a warm start from the drifted trunk reads 0.32 ± 0.026 after iteration 0 (the recovery cell) and 0.30 would halt it falsely; from the second segment the plateau (0.42–0.45) is established and the floor rises to 0.30, under which the anchored recipe has never been seen. A guard halt costs a check-in and a relaunch, not the run.

### 3. Shape: one loop in six weekly segments, segmented by its wall budget

The run is ONE loop (one `loop_state.json`, one replay window, one day-zero state-ranking row, one ladder of `iter-NNN`), launched with `--wall-hours 168`. At the wall stop the loop closes between iterations and the chain runs the segment's reads (§4); the next segment is the same command relaunched with the budget raised by 168 h (`wall_used_s` persists, so the loop resumes at the next iteration with its window and provenance intact). Six segments = 1,008 h, the plan's full envelope. Continuing past a segment is the user's go; a halt is not relaunching.

Chained separate loops were considered and rejected: the optimizer is rebuilt every iteration so nothing is lost there, but each fresh loop would train on only its own stores for the first few iterations (≈ 4.5 h of thinner mixture per boundary), restart the drift series the kill rule reads, and split the ladder across six names.

**What an interruption costs.** `anvil.runs pause` writes STOP into the loop root only; the loop exits at the next iteration boundary (≤ 1.5 h, ≈ 45 min on average; the iteration length is stable because the replay window is bounded) with nothing lost. A reboot or crash resumes from the state file: ingested batches and a completed training step are reused, the batch in flight regenerates — at most ≈ 35 min (the 240-game mirror batch), and the wall budget carries across the resume.

Sizing from the rung-2 cell's measured cadence: 480 games and ≈ 1.5 h per iteration (≈ 320 games/h), so ≈ 110 iterations and ≈ 53K games per segment, ≈ 670 iterations and ≈ 320K games at six. Disk ≈ 650 MB per iteration (checkpoint + two stores) ≈ 440 GB over the run against 2.0 TB free.

### 4. Reads, pre-registered

- **Segment close (every 168 h, on the loop's final checkpoint):** 2,000 games network-alone (`final_read.py --skip-ante`, 24 workers, one fixed seed set for the whole series so checkpoints pair across segments) and 1,000 games with-lookahead under `$RECIPE`. Both raw. The per-iteration state-ranking Spearman row and the per-5-iteration 200-game arms row are the in-loop trend meters; they never decide.
- **Segment 1's close (≈ 50K games)** re-issues the power statement's slope from the run's own curve (the plan's 50K-game checkpoint).
- **Segment 3's close is the mid-point**, where the kill rules below are adjudicated.
- **The close of the run:** the standard 2,000-game read on fresh seeds (the number of record) plus the paired read against the era reference at 2,500 games per seat (SE ≈ 0.7pp).
- Mid-run reads are for guards, the gap and the Spearman only (the plan's rule); nothing else is read from the run before its close.

### 5. The bar and the kill rules, in numbers

- **Promotion:** ≥ +2.5pp network-alone over the era reference at 2,000 games — **≥ 0.559** against 0.534 ± 0.011 — promotes the checkpoint that reads it (the standing gate, ADR-0115). The paired close read is the confirming number.
- **Kill (the teaching channel):** at segment 3's close, with-lookahead ≥ 2 SE above its masked start point (read in the chain's first step) while network-alone is within 1 SE of the warm start's masked read — adjudicate capacity / encoding, not more compute.
- **Tripline (the leaf caps both):** both series flat at segment 3 while the Spearman is flat — back to the value head.
- **Tripline (the third shape, ADR-0118):** the Spearman falls more than 2 boot SE below the day-zero build's 0.374 while network-alone is flat — the guard halts the loop (floor 0.30 from segment 2); a run whose anchored head still falls stops for a value-head pass.
- The kl / entropy / veto / casts guards stand at their settings-pass values.

### 6. Power statement (raw)

*Detect:* the 2,000-game read resolves ± 1.1pp, so the +2.5pp bar is 2.3 SE single-arm; the paired close resolves 0.7pp, so a +2.5pp effect reads at 3.6 SE. *Produce:* the shakedown's alloc arm gained +2.2pp in 30 h from day-zero; the rung-2 cell gained +0.85pp in 30 h (inside noise of each other). If a quarter of alloc's slope holds, the bar clears inside the first segment; the slope of record is re-issued from the run's own curve at segment 1's close.

### 7. Operations

Launched through `anvil.runs launch` with `--resume-on-gone`, `--watch` on the loop root and the chain's read dirs, `--stall-min 180`; `nice 19`; the kernel, the open nvidia module, `nvidia-utils` and the JDK pinned in `IgnorePkg` from launch to close (in place since 10-05). Kopia's hourly snapshots cover the 440 GB growth. The one human step on any reboot is the LUKS passphrase. The launching session owns the close (ADR-0107).

## Consequences

- **One prerequisite before the launch command:** `scripts/big_run_chain.sh` written as the recipe's single source (the start-point reads, the segment loop, the segment reads, the relaunch with the raised budget). The `CensusRun -certify` + `PayDirective` deletion is deferred to the next boundary: dead code off the game path, and a tip change on launch day would cost a jar and a forkcheck. **The `payment-evalset-v2` re-certification goes with it (user, 10-05 evening):** the recipe of record passes no `--pay-labels`, so nothing in the run trains on or reads the evalset; its re-certification was tied to the old certifier's deletion (ADR-0117: the M9 set re-certifies through the witness, new drills mine on AnvilRun's construction) and is a build-and-read item of its own, routed by name to the boundary that deletes the certifier.
- **Routed, not blocking, stated here so they are not lost:** the 38% re-ask rescue rate (a census read); the slow trunk lr's own strength cost (read on the run's curve, not before it); the two-mask agreement comparison with Kryptic's enumerator (a maintenance window once the run is up); the amortized advantage head behind a critic upgrade (ADR-0119 step 4); Fork H (the Android ship of `iter-019`) on the playable branch during the run.
- **A standing rule is born:** a long run is segmented by its wall budget, never by chained loops — the review point is the loop's own wall stop, the reads are the chain's, and the next segment is the same command with the budget raised.
- The plan's Build 5 item reads from this ADR; its closeout (Build 6) is the standard 2,000-game read plus the paired close read, the ladder of own checkpoints, and the queue routed by name.
