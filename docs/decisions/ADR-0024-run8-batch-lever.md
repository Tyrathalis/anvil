# ADR-0024: run-8 batch-lever verdict — negative; the residual defect is absent signal, not gradient noise

Date: 2026-07-25
Status: accepted

## Context

D2 closed (ADR-0023) with run-7b's supersession and a ceiling datum: the
standing recipe (§6d mix + §6c penalty + §6f critic, lr 1e-5, 480 g/iter)
went flat in its own tail (i14 0.5625 → i19 0.5475 on 400-game arms). The
early-doom analysis (2026-07-23) showed the eval ceiling is NOT luck-bound
(luck-locked losses 18–39%; ceiling 0.83–0.92 vs 0.5530), so a scaling
probe was justified before the D4 rebase freezes the fork lineage. The
credit diagnosis from the τ falsification (§6e) said the residual defect
lives in near-tie windows whose advantage is essentially random — the
hypothesis was that halving gradient variance would let real signal
dominate.

d6-run8 = run-7b verbatim, init `run7b/iter-014/{train,critic}`, except
the one coherent lever: `--games 960 --traj-per-step 8` (same optimizer
steps per iteration, half the gradient variance per step) with
`--critic-steps 4000` (preserves the §6f one-pass pin at 2× store size).
Fresh seeds 20260820.

## What happened

- **Trajectory (400-game arms, standard paired seeds):** i4 0.5325 → i9
  0.5275 → i14 0.5675 (nominal high-water of any run) — no early dip,
  flat consolidation, apparent late climb.
- **Stability:** veto oscillated 0.11↔0.18 all run (run-7b: 0.08↔0.13),
  then diverged: **guard halt at iteration 18** (veto 0.217 > 1.5×
  baseline; KL 3× step to 0.033; §6 anomaly rule fired concurrently —
  shaped reward 0.383 vs masked head 0.492). Iterations 0–17 accepted,
  18 rejected. Zero mid-run incidents otherwise.
- **The decision read (2,000 games, `final_read` protocol, record
  `data/runs/run8-best-arms-report.json`):** i14 corrected **0.5340 ±
  0.0110**; paired vs run7b-iter-014 on the same seeds: **−2.00pp ± 0.99
  (t=−2.03, 175 up / 215 down)**. The 400-game 0.5675 was a ~1.3σ
  flattering read — the promotion protocol (2,000-game paired) did its
  job.

## Decision

- **Checkpoint of record UNCHANGED: `d6-run7b/iter-014/train/last.pt`.**
- **The batch axis joins the falsified-lever list.** Two independent
  probes now bound the recipe at this operating point: continuing at 480
  g/iter is flat (run-7b's own tail), continuing at 960 g/iter is
  slightly negative with a stability cost (run-8). The recipe family is
  at its ceiling.
- **Diagnosis sharpened: the near-tie residual is absent SIGNAL, not
  gradient noise.** If advantage noise were binding, variance halving
  should have helped; instead it trained ~equally then drifted. The
  reward genuinely does not distinguish near-tie windows — averaging
  more zeros is still zero. Reaching the (large, measured) remaining
  headroom needs a *different signal source*: Grindstone drills
  (ground-truth positions from the early-doom curation list), rollout
  labels (the parked D4 machinery, now cheaper under micro-batching), or
  post-rebase levers.
- **Stability note (extends ADR-0017):** lr brackets are per-signal-
  regime AND per-batch-size — 2× batch at lr 1e-5 sits near the
  stability edge (wide veto oscillation → divergence at iter 18). Any
  future scale run at this lr should assume it is edge-adjacent.
- **Consequence for M3 sequencing: proceed to the D4 rebase.** The RL
  era of this fork lineage ends with the record at 0.5530. Grindstone
  design (M4) inherits the curation list + this ADR's signal-source
  argument.

## Price

~40 GPU-hours (18 accepted iterations + reads). Bought: the batch lever
resolved, the absent-signal diagnosis, the stability-edge datum, and a
validated promotion protocol catching a false positive.
