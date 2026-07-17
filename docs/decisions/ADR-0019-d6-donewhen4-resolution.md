# ADR-0019: done-when #4 resolves TRUE — V-trace self-play improves the arms outside noise

- **Date:** 2026-07-17
- **Status:** accepted
- **Design-doc anchor:** m2-rl-plan §D6 done-when #4; d6-vtrace-loop §4/§6 (as amended by ADR-0017)

## Context

M2's final open gate: *"V-trace improves the arms outside noise."* Run-1
(lr 1e-5 × 12) read +3.76pp ± 2.22 (t=1.69) — improves, not outside noise.
Run-2 (lr 3e-5 × 16) collapsed (ADR-0017). Run-3 was the first guarded run:
lr 2e-5 × 20 planned, hinge entropy floor, halt triplines, re-ask
environment, init = run-1's final checkpoint.

## What run-3 did

- **13 healthy iterations, then a clean self-halt.** Entropy stayed pinned
  0.17–0.21 the whole run (the ADR-0017 hinge holding where run-2 tripled by
  iteration 4); per-iteration KL 0.013–0.029, never near the 0.05 tripline;
  critic tracked reward two-sided. At iteration 13 the **veto guard fired**
  (41.3% > 1.5× the 25.1% baseline) and the driver rejected the checkpoint
  and exited 3 — the first live guard halt, ~10 minutes of wasted compute
  vs run-2's ~5 hours.
- **Strength grew monotonically while veto drifted:** arms at init 50.75 →
  iter-4 50.0 → iter-9 52.5 → iter-12 (last accepted) 54.75 (400-game
  reads). The drift and the strength gain are so far co-travelers, not a
  trade the guards forced us out of prematurely — but 41% veto means ~2 of 5
  cast intents were engine-rejected at the end; the drift is real.
- En route, two GPU-cotenancy OOMs beside a resident ComfyUI (10.45 GiB)
  were diagnosed and durably fixed (expandable-segments allocator baked into
  the driver; `--rl-seg` peak-halving knob; VRAM-elasticity QoL item queued).

## The resolving read (record `data/runs/run3-final-arms-report.json`)

2,000 games (2×1,000 mirrored, paired-seed base 20260710, argmax, `-reask`,
obs on), checkpoint `d6-run3/iter-012/train/last.pt`:

- **Raw 0.5220 ± 0.0112; Ante-corrected 0.5213 ± 0.0110** (1,995 decisive,
  5 crashes; ledger zero-mean; 4 certify reports in `data/runs/ante-run3-*`).
- **Paired vs the D5 BC arm (400 shared seeds): +6.75pp ± 2.31, t=2.92 —
  outside noise.** Paired vs its own init (run-1 final): +3.75pp ± 2.16
  (t=1.74) — run-3's marginal contribution is suggestive on its own; the
  cumulative RL chain (BC → run-1 → run-3) is what clears the gate, which
  is what the gate asks.
- Absolute milestone: the agent is ~2σ above parity with the heuristic
  teacher it was cloned from — the first credible teacher-surpassing read
  in the project.

## Decision

1. **M2 done-when #4 is SATISFIED.** All four M2 done-when clauses are now
   resolved (fork contract + PR #11203 merged; SA checkpoint + repriced
   arms; critic over the floor + Ante certified; V-trace outside noise).
   Formally closing M2 (and opening M3 planning) is the next session-level
   decision with the plan doc — this ADR resolves the gate, not the
   milestone.
2. **`d6-run3/iter-012/train/last.pt` = RL checkpoint of record.**
3. **Veto drift is the named open front for the next run.** The guard halt
   is a feature doing its job, but 25→41% over 13 iterations under a
   plugged leak (re-ask) says the *policy* is still learning to prefer
   engine-rejected casts. Levers, in rough order: a small veto penalty in
   the reward (prices the drift directly — but touches §3d reward
   semantics, needs its own pin), first-attempt veto rate as the monitored
   quantity (chains inflate the current metric), per-head entropy floors
   (the ADR-0017 contingency, also independently suggested by Austinio's
   survey), and X-factor inclusion refinement (the standing watch item).
4. Guard calibration stands as-is (the 1.5× veto tripline did its job);
   revisit only with the veto-penalty work.

## Consequences

- Status/map updated; devlog 2026-07-17 carries the session narrative.
- Selection-honesty note: iter-012 was chosen as the chain's endpoint (last
  accepted ckpt), not cherry-picked — its quick read (54.75) regressed to
  52.20 at 2,000 games, as quick reads do; the resolving stats are from the
  large read only.
- The M3-shaping questions this run surfaces: veto-drift economics (per
  decision #3), arms cadence vs guard granularity (a halt costs at most one
  iteration of compute now), and whether the ~10% rescue rate justifies
  re-ask's ~1% request overhead permanently (it does today; re-price if
  veto rate is driven down).
