# ADR-0124: The anchor bank refresh — the value anchor memorizes its bank; segment 3's states under fresh rollout truth, the offline head refit, the anchor draw budget; the 0.3 anchor arm retired

- **Date:** 2026-10-29
- **Status:** accepted; **§2–3 (the fixed segment-3 bank, the offline refit) superseded 10-29 evening by [ADR-0125](ADR-0125-value-head-track.md)** (rollout truth as a stream, the full-vis critic, the distilled head; after the big run) — §1, §4 and §5 stand
- **Design-doc anchor:** §3e (the value head under the loop), §7 (the value function audited against rollouts); amends [ADR-0123](ADR-0123-big-run-launch.md)'s boundary interventions and [ADR-0118](ADR-0118-value-head-drift-under-the-loop.md)'s anchor

## Context

Segment 3 of the big run closed 10-29 with `iter-301` promoted (+6.32 ± 0.79pp paired over the era
reference on fresh seeds) and the state-ranking Spearman at 0.326 ± 0.027 on the frozen holdout — the
ADR-0118 line reached as the segment-2 review projected. The pre-registered response was the anchor
arm: the head-only anchor weight 0.1 → 0.3 from `iter-301`, paired against a continuation. Two reads
at the boundary changed the attribution before the arm ran.

**The head-swap read** (`value_pretrain eval --swap-head`, `data/runs/big-run/swaphead-seg3.jsonl`):
`iter-301`'s trunk under its own head 0.326; under `iter-099`'s head 0.325; under the warm start's
head 0.349; under `settings-recovery/iter-006`'s head **0.409 ± 0.023** — above the day-zero build's
0.374. The converse, `iter-099`'s trunk under `iter-301`'s head, 0.308 from 0.398. The trunk's
features still rank; the run's own head is the worst head on every trunk. The 09-24 attribution on the
un-anchored shakedown (the drift in the trunk) does not carry to the stop-grad recipe: here the loss is
the head's.

**The memorization read.** The anchor term (ADR-0118 item 3) trains the head each optimizer step on
96 rows drawn from the Build-1 bank's 8,403 non-holdout rows (`labelset-c2-v3`: K=8 rollout win rate
at pre-action states, August states, iter-019-era rollouts). Its own training loss fell monotonically
across the run — 0.69 (iteration 1) → 0.53 (25) → 0.37 (100) → 0.29 (200) → 0.19 (300) — while the
holdout Spearman peaked at 0.48 (iteration 25) and slid to 0.33. Scored on all 9,600 bank rows
(87% training rows) against the frozen holdout (1,197):

| ckpt | anchored iterations | holdout ρ | all-rows ρ |
|---|---|---|---|
| `shakedown-alloc/iter-019` (never anchored) | 0 | 0.250 | 0.255 |
| `settings-recovery/iter-006` | 6 | 0.439 | 0.457 |
| `big-run/iter-099` | 99 | 0.398 | 0.714 |
| `big-run/iter-301` | 301 | 0.326 | 0.840 |

Exposure: 340 optimizer steps × 96 rows = 3.9 passes over the bank per iteration, ≈ 1,170 passes over
the run, on a 263k-parameter head over a near-frozen feature map (stop-grad; trunk lr 3e-6). The head
has learned the bank by heart (≈ 0.90 on the training rows alone); once it has, the anchor's gradient
goes quiet and the V-trace term alone sets the ranking on states the head has not seen — and V-trace
alone lands near 0.25 on this bank (the no-anchor control, 10-04). The recovery cell looked good because
24 passes had not yet memorized. The leaf family (799 windows, ≈ 0.4 pass per iteration; loss 0.97 →
0.75) shows the same direction more slowly. The loop's per-iteration Spearman row is on the holdout and
was honest throughout.

Two consequences follow. A heavier anchor weight should memorize faster, not hold better — the premise
of the 0.3 arm is gone. And the remedies are of the data and the schedule: a bank the loop cannot
memorize within a segment, on the states and under the rollout policy the leaf now serves.

## Decision

1. **The 0.3 anchor-weight arm is RETIRED unrun** (the user's call, 10-29). The prediction is recorded:
   under the attribution above, weight 0.3 from `iter-301` would lower the anchor's training loss
   faster and leave the holdout where it is or lower. The rolls-4 arm's condition (the Spearman
   holds) was not met; its with-lookahead read on `iter-301` runs as exploratory only.
2. **The segment-3 bank.** States sampled from segment 3's self-play stores (iterations 203–301),
   turn-stratified as the labeler's standing configuration draws them, **≥ 40,000 states** — sized so
   one iteration's anchor draws at the current rate (32,640 rows) stay under one pass — with a
   **game-hash holdout of ≥ 10% frozen** at the bank's birth. Labels: the standing rollout labeler
   (`-rollout 8`), served by `iter-301` network-alone on the launch jar, census off. Priced first by
   `scripts/bench_labeler.py` on the quiet box; the bank is `data/runs/seg3-bank/`.
3. **The offline head refit.** The value head alone, the trunk frozen at `iter-301`'s weights, the
   Build-1 fit's state terms (RankNet pairs, |Δwr|-weighted, gate 0.2, + 0.05 BCE on wr), early-stopped
   on the new holdout's Spearman; the old holdout scored beside it for continuity. The checkpoint is
   `data/training/big-run/iter-301-refit/train/last.pt` (config key `head_refit` naming the bank and the
   stopping epoch). **Bars:** network-alone identical by construction (a 500-game smoke within noise of
   `iter-301` confirms the policy path untouched); the with-lookahead paired read vs `iter-301` on seeds
   20261006 (1,000 games) flags below −1.0pp or beyond 2 SE; if the transplant read (`rechead-read`)
   widened the lookahead gap, the refit head must match the transplant head's gap within 1 SE or beat
   it — otherwise the transplant head serves segment 4 and the refit is read as a miss.
4. **The online anchor from segment 4.** The state family draws from the segment-3 bank (the Build-1
   bank's state rows retire from the anchor; the leaf family is retained unchanged, one change at a
   time, and gets its own read — see Consequences). **The draw budget is a flag** (`--anchor-every K`:
   one anchor mini-batch every K optimizer steps) set so one iteration's draws are **≤ 0.25 pass** of
   the bank. **The memorization meter:** the per-iteration Spearman row gains the anchor's
   training-row score beside the holdout's; **train − holdout > 0.15 is a pause line** (read, then
   the user's call). Built in a worktree, smoked on a short cell before segment 4.
5. **Meter continuity.** The Spearman floor and the ADR-0118 line re-base on the new bank: the refit
   head's holdout score on the segment-3 bank is segment 4's day-zero; the floor is 0.80 × day-zero
   for segment 4 (the ADR-0123 ratio for a stabilized head); the old holdout stays a per-iteration
   column for the record. Nothing else in ADR-0123 changes: the kill rules, the wall segments, the
   promotion bar, the seed base and the reads.
6. **Sequencing.** The transplant read first (it decides urgency: a widened gap means the leaf's
   ranking caps the search and this work precedes segment 4; an unchanged gap means it is hygiene and
   segment 4 may continue under the draw budget alone — the user's call either way). Then the labeler
   re-price, the bank, the refit, the reads, and segment 4 from `iter-301` with the head of record
   under the amended anchor.

## Consequences

- **Standing rule (births one):** an anchor bank is read on its training rows beside its holdout; a
  growing gap is memorization; size the bank and the draw budget so one iteration stays under a pass;
  never raise the anchor weight to fix a sliding holdout.
- **ADR-0123's boundary interventions amended:** the anchor arm retired (this ADR); the rolls-4 read
  exploratory. ADR-0118's item 3 (the anchor) stands with the bank and budget amended here.
- **Routed by name:** `--anchor-every` + the training-row Spearman column (trainer + loop; worktree,
  smoke); the leaf family's own read (it distills the full-vis critic, which binds at corr 0.16–0.20
  on the Ante re-measure — whether it helps or hurts the state ranking is unread); the head-reset
  option (the transplant as a standing move at a boundary, if the refit's read says the leaf matters);
  the bank's refresh cadence (one per run, or per segment — decided at segment 4's close on the
  memorization meter); the kl-targeted lr and the per-iteration aux recalibration stay routed from the
  segment-3 close. The M12 closeout's value-head design thread folds this in.

## Addendum (2026-10-29 evening) — the price, the draw budget and the meter built

- **The labeler price (§2's first step):** ≈ 650 labels per box-hour steady state on `iter-301` with the launch jar at
  K=8 (133 worker-seconds per label over 24 workers; a fork block p50 152 s) — the 40,000-state bank is ≈ 2.5–3.5
  box-days (62 h steady, 83 h at the observed rate with the fleet's ramp); 20,000 states or K=4 halve it. Read from a
  partial bench (85 of 160 mainlines; a harness abort guard misfired on one-game spans, fixed beside it).
- **§4 built (the `anchor-every` worktree, 10-29):** `--anchor-every K` in the trainer and the loop; the memorization
  meter — the loop's state-ranking row carries `train_spearman` (a fixed seeded sample of 2,000 of the anchor bank's
  training rows) and `gap` = train − holdout, read on the anchor's bank; the pause line `--guard-anchor-gap 0.15` accepts
  the iteration, writes a STOP the next relaunch clears, and re-bases 0.05 above the pausing gap (one-shot per level).
  `value_pretrain eval --split holdout,train` is the same read by hand. Smoked on a tiny loop (the running record).
- **Sequencing (§6) after the price:** the transplant read did not widen the gap, so the bank is hygiene, not the
  binding constraint; at ≈ 3 box-days it is not "about a day". The user's call: the bank and the refit before segment 4
  (≈ 3 idle-box days plus the refit's reads), or segment 4 now from `iter-301` under the draw budget and the meter — with
  the run's own head or the recovery head transplanted (the head-reset option routed above; its read +0.82 ± 1.20pp
  with-lookahead, network-alone identical) — and the bank built at segment 4's close. Either way the floors re-base only
  when the refit head exists; until then the ADR-0123 floor (0.30) and the ADR-0118 line stand on the old holdout.


## Addendum (2026-10-29 late evening) — segment 4 in HOLD mode (the user's go)

With §2–3 superseded by [ADR-0125](ADR-0125-value-head-track.md), the big run's remaining segments run the value head in
hold mode under §4–5, with the head-reset option taken:

- **The start checkpoint is `iter-301` with the recovery cell's value head transplanted** (`settings-recovery/iter-006`'s
  `value_head.*` tensors; bank Spearman 0.409 vs 0.326; with-lookahead +0.82 ± 1.20pp paired, network-alone identical by
  construction — the 10-29 head-swap and transplant reads). The four value-head tensors are the only difference; the
  trunk, every other head, the carries and the alloc tau are `iter-301`'s. The loop resumes at iteration 302 from its
  `loop_state.json` with `ckpt` re-pointed at the transplant (the optimizer is rebuilt every iteration, so no moments
  are discarded); the replay window, `start_index`, `alloc_w` / `distill_w` and the wall ledger continue unchanged.
- **The recipe gains two flags and no other change:** `--anchor-every 16` (≈ 21 anchor steps an iteration × 96 rows =
  2,040 rows ≈ 0.24 pass of the 8,403-row Build 1 bank; ≈ 24 passes a segment — the recovery cell's total exposure, which
  had not memorized) and `--guard-anchor-gap 0.15` (the pause line; the row's `gap` is the meter). The anchor weight stays
  0.1 (one change at a time). `-XX:+UseParallelGC` joins the worker JVMs only if the timed A/B clears (a marker file the
  chain reads; the forkcheck already passed).
- **Pre-registered expectation:** the Spearman starts near 0.41 and ends segment 4 within one SE (≈ 0.025) of its start
  with the gap under 0.15; strength is unaffected (the transplant read). **The two misses and their readings:** a
  Spearman drifting toward 0.35 with the gap near zero = the draw budget's hold is too weak against V-trace (the next arm
  is the frequency / weight trade at the same pass budget: `--anchor-every 8`, or a heavier anchor step at 16); a growing
  gap = memorization at a quarter pass (the pause line fires; read, then the user's call). Neither is a kill rule;
  ADR-0123's rules, floor (0.30) and reads stand unchanged on the old holdout.
- The track that could make the head *better* is ADR-0125's, after the run.
- **Launched 10-29 23:33** (the running record): the timed A/B cleared (paired ms ratio 0.959 / 0.984), ParallelGC on the workers;
  the loop resumed at iteration 302 from the transplant, both servers serving it, the meter's flags on the trainer's command line.

## Addendum (2026-11-02) — the segment-4 reading and the run-distribution holdout for segment 5 (the user's go)

**Segment 4's hold is more than holding, and the question it leaves is what the holdout measures.** Through iteration 347
the holdout Spearman rose from 0.432 (iterations 302–312, mean) to 0.458 (335–347): an OLS slope of +0.020 per 25
iterations, t 8.5, a row-to-row scatter of 0.008 around the line (the quoted 0.028 per row is the fixed holdout's
bank-sampling SE, shared by every row). Train rose 2.4× faster (+0.047 per 25) and the gap went −0.017 → +0.021 across
the segment: memorization at about a quarter of the pre-ADR-0124 rate, the pause line (0.15) ≈ 140 iterations out at
that pace. Strength is flat within noise across the nine arms rows (0.535–0.5875 network-alone, SE 0.025). Neither
pre-registered miss fires. **The caveat:** the holdout is drawn from the same Build 1 bank the anchor trains on, so the
rise reads generalization inside that bank's state distribution, not to the states the run plays.

**Decision for the segment-5 boundary — a measurement, not a training change:**

1. **A second, run-distribution holdout, added beside the Build 1 one.** ≈ 2,000 states sampled from segment 4's own
   stores, stratified by turn and phase as the Build 1 bank was, labelled by the fork's K=8 labeler under segment 4's
   close checkpoint (≈ 3 box-hours at the measured 650 labels per box-hour), then FROZEN. The loop reports its Spearman
   as a second row (`spearman_run`) every iteration of segment 5. Its floor for segment 5: the boundary value minus two
   SE; exploratory on its first segment (no kill rule hangs on it).
2. **The Build 1 holdout stays.** It is the continuity series from 302 and the ADR-0118 reference line; it is not swapped.
3. **No periodic regeneration mid-run.** Rollout labels depend on the labelling checkpoint, so a rolling holdout would
   confound the head improving with the labels moving; a frozen per-segment holdout with a fresh one at each boundary is
   the shape [ADR-0125](ADR-0125-value-head-track.md) proposes for the stream, which stays the next milestone's center.
4. **The anchor is unchanged.** The recipe of record names the Build 1 bank; changing what the anchor trains on is a
   recipe change and belongs to the closeout. The 10-29 head-transplant read (ranking not the strength cap at the 1pp
   level) argues for measuring before investing.

**Reading at segment 5's close:** if the Build 1 rise transfers (the run-distribution row rises or holds over the
segment), the hold is doing real work on the leaf; if it does not, that is the strongest case yet for the stream.
Built in a worktree before the boundary (no tree edits under the running loop); the flags join the quickstart's §7
table and the chain.

**Amendment (11-02, after the build):** "sampled from segment 4's own stores" reads as **the labelling run's mainlines**.
The fork's labeler forks LIVE games at sampled quiescent MAIN1 priority windows (`-rollout K -points M`) and cannot
restore a stored state (a model-played game is not reproducible under another checkpoint's serving); the Build 1 bank was
built the same way. So the run-distribution holdout's states are the close checkpoint's own games — argmax,
network-alone, census off, the loop's mix (half mirror, a quarter per heuristic seat), ≈ 500 games with K=8 at 4 points
each (≈ 3 box-hours) — labelled by the same run and ingested; the sampler draws ≈ 2,000 fork points from them,
stratified by turn (the labeler's uniform draw over turns 2–16; phase is MAIN1 by construction). The bank is written in
the Build 1 layout (`bank-state.pt` with `wr` in its meta; one split, `holdout`; `manifest.json` with `frozen: true`),
so `_state_ranking()` reads it unchanged. Built on branch `worktree-agent-a21b710731bc8fc46` (two commits on `f8ba9b2`:
`value_pretrain bank-run` + `scripts/run_holdout_bank.py label|sample|read` + `selfplay --state-bank-run` /
`--guard-spearman-run-floor` + the chain's `RUN_BANK` / `RUN_FLOOR` hook, off; procedure in
`docs/design/run-holdout-bank-read.md`; 9 new tests). Merged at the boundary, not before (no tree edits under the loop).
The smoke's one number worth keeping: on the 10-29 labeler bench's 85 mainlines (K=8 under `iter-301`, 40 sampled
rows), `iter-301` ranks at 0.80 ± 0.06 and `iter-347` at 0.83 ± 0.06 — far above the Build 1 holdout's 0.47 on the same
checkpoints: the head ranks its own policy's states much better than Build 1's, so **the run-distribution row's level is
its own and its floor comes only from the boundary read**.

## Addendum (2026-11-07) — the segment-4 bank built and read: the hold does not show on the run's own states

**The bank** (`data/runs/run-holdout-seg4`; its `read.md` and `manifest.json` are the record and the pin): 500
mainlines of `big-run/iter-405` on the loop's mix (250 mirror, 125 per heuristic seat; argmax, network-alone, census
off, the launch jar), K=8 at 4 fork points, seed base 20261107 — 1,902 labels in 3.8 productive box-hours (≈ 500 per
hour; a 2.8 h yield to a foreign GPU job sat inside the 6.7 h wall); the draw took every candidate, 1,894 rows over 15
turn strata (t2–t16, all MAIN1). The chain's `RUN_BANK` names it with `RUN_FLOOR` 0 (the first segment's letter:
exploratory, no rule on the row).

**The boundary read** (`spearman_run`, n 1,894): `iter-405` **0.764 ± 0.010**; `iter-301` 0.766 ± 0.010;
`iter-301-rechead` (the segment-4 start) 0.755 ± 0.010; the never-anchored `shakedown-alloc/iter-019` 0.759 ± 0.010.
**The four points lie within one SE of each other.** On the Build 1 holdout the same four span 0.20 (0.250 never
anchored, 0.326 `iter-301`, 0.4205 the transplanted start, 0.452 the close). So the anchor's hold moves the ranking
inside the Build 1 distribution and leaves the ranking of the states the run plays where it was — every head in the
lineage ranks those at ≈ 0.76, labelled by the run's own rollouts. A labeller bias toward the labelling head would show
as `iter-405` above the never-anchored head: +0.005 ± 0.014.

**What it changes.** The Build 1 row is confirmed as the continuity meter and the anchor as hygiene for it, not as a
lever on the leaf — the same conclusion the 10-29 transplant read reached on the lookahead gap (inside one SE), now on
the ranking itself. The 11-02 reading pre-registered for segment 5's close ("the run row rising or holding while the
Build 1 row rises = real work on the leaf; flat or falling = the case for the stream") is already answered at its
start for the segment-4 hold: it did not transfer. The segment-5 row still earns its place as the collapse guard on the
leaf the search actually uses, and as the first series of its kind; its reading at the close is whether segment 5's
training moves it at all. The stream ([ADR-0125](ADR-0125-value-head-track.md)) keeps its routing to the closeout
scoping; nothing here advances or retires it. The gap's response for segment 5 (a wider `--anchor-every`, or the pause
line as the registered response) is unchanged by this read and stays the user's call.
