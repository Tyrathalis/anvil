#!/usr/bin/env bash
# d6-run15 — the M7 C-bundle run, take 2 (ADR-0056: run14 GUARD-HALTED at
# iter 2 on the unbounded L_seq runaway; no gate read). Base =
# launch_d6_run14.sh verbatim; deltas = the ADR-0056 amendment (L_seq
# hinge --seq-margin 6.0, seq_share guard --guard-seq-share 0.3, battery
# seq trend, in-phase kl abort at 5x guard-kl) + fresh seed_base 20260815.
# Restarts from iteration 0 (run14's iter-000/001 ckpts carry veto damage).
# Gate: standing combined paired read vs 0.5373 +/- 0.0112 (ADR-0055, era
# d798917ae5). Pre-registered secondary read (NOT gate-bearing, ADR-0056):
# holding same-turn hold-then-cast should move TOWARD heur ~0.345.
# ~2h45m/iter measured on run14 -> ~55h total.
#
# GATE ON THE SMOKE: launch only after launch_seqfix_smoke.sh passes
# (seq_share flat across its iteration boundary, |seq_raw| bounded).
#
# Launch checklist (the detached-run-launches memory): setsid nohup this
# script; the driver self-registers watchd and self-unregisters; ALSO arm
# a persistent log monitor (GUARD HALT / ANOMALY / battery anomalies /
# Traceback / KL ABORT) + periodic telemetry glances.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python -m anvil.training.selfplay \
  --name d6-run15 \
  --ckpt data/training/d6-run11/iter-019/train/last.pt \
  --iterations 20 --games 480 --games-per-pair 2 \
  --workers 8 --chunk 30 --port 50063 --seed-base 20260815 \
  --temperature 1.0 --replay 4 --fresh-weight 1.0 --replay-weight 0.33 \
  --rl-workers 12 --epochs 1 --lr 1e-05 \
  --ent-weight 0.003 --ent-floor 0.08 --rl-seg 128 \
  --guard-kl 0.06 --guard-ent-mult 2.0 --guard-veto-mult 1.5 \
  --guard-casts-floor 0.8 --guard-seq-share 0.3 \
  --penalty 0.01 --penalty-grouping first --heur-frac 0.5 \
  --critic data/training/d6-run11/iter-019/critic/last.pt \
  --critic-lr 1e-05 --critic-steps 2000 --critic-batch 256 \
  --value-weight 0.5 --traj-per-step 4 --reask \
  --arms-every 5 --arms-pairs data/runs/d5arm-d0-s0-20260714-143546/pairs.txt \
  --arms-games 200 --arms-seed-base 20260710 \
  --drill-eval-set data/runs/drill-evalset-v4 --drill-eval-every 5 \
  --drill-selection data/runs/drill-selection-v5-active/selection.jsonl \
  --drill-points-per-iter 99 --drill-k 2 \
  --drill-replay-ckpt data/training/d6-run11/iter-019/train/last.pt \
  --seq-n 4 --seq-k 16 --seq-margin 6.0 \
  --drill-windows-only --overlap-campaign --campaign-workers 16
