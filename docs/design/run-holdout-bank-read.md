# The run-distribution holdout — building the bank at a segment boundary and reading it

**Doc status:** reference · the segment-boundary recipe for the second, frozen state-ranking holdout ([ADR-0124](../decisions/ADR-0124-anchor-bank-refresh.md) 11-02 addendum); the per-bank `read.md` is this file filled in

## What it is

A second state-ranking holdout, drawn from the big run's own games, read by the loop every iteration as
`state_ranking.spearman_run` beside the Build 1 holdout's `spearman`. The Build 1 holdout is drawn from the
bank the value anchor trains on, so its rise in segment 4 reads generalization inside that bank's
distribution; this bank says whether the movement transfers to the states the run plays. Every row is
`holdout`; nothing trains on it; the anchor never names it; one bank per segment boundary, never
regenerated mid-segment (rollout labels depend on the labelling checkpoint, so a rolling holdout would
confound the head moving with the labels moving).

**What the labeler can do.** The fork's rollout labeler forks LIVE games (`-rollout K -points M`: at `M`
quiescent MAIN1 priority windows on uniform distinct turns it copies the game and plays `K` completions to
the end, one labels row per fork point, a `fork` mark in the store frame keying the point to the next
mainline window). It cannot restore a stored state, and a model-played game is not reproducible under
another checkpoint's serving. "The run's own games" are therefore the labelling run's mainlines: the
segment's close checkpoint, argmax, network-alone, census off (the labeler's standing configuration),
playing the loop's mix — half mirror, a quarter each heuristic seat (`--heur-frac 0.5`) — recorded with
`--obs` and ingested with their labels. The states are then drawn from those stores stratified by turn ×
phase (the Build 1 bank's turn-stratified fork points; phase is MAIN1 by the fork's construction and is
recorded). The perspective is the model seat in a heuristic-seat store and the window's own player in a
mirror store; `wr` = that seat's wins / (wins + draws), the labelset's definition.

## The procedure (the boundary session, the box quiet — the loop paused or at its wall)

1. **The labelling run** — ≈ 3 box-hours at K=8 (the 10-29 price: ≈ 650 labels per box-hour on `iter-301`
   at 24 workers × 2 servers; a fork block p50 ≈ 150 s). 500 mainlines × 4 points ≈ 2,000 labels (a few
   percent fewer after crashed completions and lost frames).

   ```bash
   uv run python scripts/run_holdout_bank.py label --out data/runs/run-holdout-seg4 \
       --ckpt data/training/big-run/iter-NNN/train/last.pt --games 500 --workers 24 --seed-base 20261102
   ```

   Through the launcher when it should survive a reboot and alert:
   `uv run python -m anvil.runs launch --name run-holdout-seg4 --dir data/runs/run-holdout-seg4 --launched-by '<name> [<ref>]' -- uv run python scripts/run_holdout_bank.py label ...`.
   The run dirs are `data/runs/runbank-seg4-{mirror,h0,h1}-<stamp>`, the stores
   `data/trajectories/runbank-seg4-*` (ingest keeps `labels.jsonl` beside the frames), the record
   `data/runs/run-holdout-seg4/label.json` (ckpt, jar, K, points, seed base, run dirs, stores, labels, labels/h).

2. **The draw** — CPU, seconds.

   ```bash
   uv run python scripts/run_holdout_bank.py sample --out data/runs/run-holdout-seg4 --n 2000 --seed 20261102
   ```

   Writes `bank-state.pt` (the Build 1 layout: `examples` + `meta` with `idx` / `wr` / `holdout: true`) and
   `manifest.json` (kind, `frozen: true`, `split: holdout`, the seed, `n_rows`, `n_candidates`, the
   labelling checkpoint, `rollout_k`, the completions histogram, `strata_sampled` / `strata_pool` by
   `t<turn>|<phase>`, the stores with their pins). `--stores` and `--label-ckpt` default to `label.json`'s.
   The same seed on the same stores is the same bank.

3. **The boundary value** — CPU, seconds per checkpoint.

   ```bash
   uv run python scripts/run_holdout_bank.py read --out data/runs/run-holdout-seg4 \
       --ckpt data/training/big-run/iter-NNN/train/last.pt
   ```

   Appends to `boundary-read.jsonl` and prints `spearman_run ± SE` and the floor at the addendum's letter
   (the value minus two SE). Read the labelling checkpoint and, for the record, `iter-301-rechead` (the
   segment-4 start) and the never-anchored `shakedown-alloc/iter-019`. Expect a different level from the
   Build 1 series: the smoke on the 10-29 labeler bench (iter-301's own states and labels, 40 rows) read
   0.80 where the Build 1 holdout read 0.47 — the floor comes from this read, never from the Build 1
   numbers.

4. **Point the chain at it** — `scripts/big_run_chain.sh`: set `RUN_BANK` to the bank dir and `RUN_FLOOR`
   to the floor (0 = exploratory, the first segment's letter: no kill rule hangs on it), by uncommenting
   the marked line or by `RUN_BANK=... RUN_FLOOR=... ` in the relaunch's environment — the chain adds
   `--state-bank-run "$RUN_BANK" --guard-spearman-run-floor "$RUN_FLOOR"` to the loop. Then the next
   segment as usual: `echo N > data/runs/big-run/segment && uv run python -m anvil.runs relaunch --name big-run`.
   The row lands in `monitor.jsonl` (`state_ranking.spearman_run`, `se_boot_run`, `n_run`, and since 11-07
   `spearman_run_contested` / `se_boot_run_contested` / `n_run_contested`: the holdout rows with rollout
   winrate in (0.2, 0.8)) and per iteration in `iter-NNN/state-ranking-run.json`; the loop's log line says
   `run bank X ± SE (contested Y ± SE, n N)`.

5. **The record.** Fill the table below into `data/runs/run-holdout-seg4/read.md`, the running record and
   the ADR's addendum; the bank's `manifest.json` is the pin.

## The read at the next boundary

| point | ckpt | spearman (Build 1 holdout) | spearman_run (this bank) | n_run | note |
|---|---|---|---|---|---|
| the labelling checkpoint (segment N's close) | `iter-NNN` | | | | the boundary value; the floor = value − 2 SE |
| the segment-N start | `iter-301-rechead` | | | | continuity |
| never anchored | `shakedown-alloc/iter-019` | | | | the no-anchor reference |
| segment N+1's close | `iter-MMM` | | | | the reading: did the Build 1 rise transfer? |

**Reading (the addendum):** the run row rising or holding over the segment while the Build 1 row rises =
the hold does real work on the leaf; the run row flat or falling while the Build 1 row rises = the strongest
case yet for the stream ([ADR-0125](../decisions/ADR-0125-value-head-track.md)). Exploratory on its first
segment; the floor is a collapse guard, not a verdict.

## The smoke (what proves the plumbing, no GPU)

Run 11-02 in the build worktree beside the live loop: the 10-29 labeler bench's run dir
(`data/runs/labelbench-w24-20261029-202126`: 85 mainlines, 343 K=8 labels on `iter-301`) ingested to a scratch
store, `value_pretrain bank-run --n 40` drawing 40 rows over 15 turn strata (all MAIN1), `read` on
`iter-301` / `iter-347` (0.80 / 0.83 ± 0.06, n 40), and the loop's `_ranking_meter` producing the row with
`spearman_run` beside the Build 1 fields; the `label` step itself smoked with a CPU server, one worker,
two games, K=1, two fork points (`--device cpu --no-autocast --no-yield-gpu --dest-root <scratch>`).
