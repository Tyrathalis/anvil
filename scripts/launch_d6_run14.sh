#!/usr/bin/env bash
# d6-run14 — the M7 C-bundle run (user-approved 2026-08-12, launched from a
# fresh session per the 08-12 session-6 devlog). Base = run13 verbatim;
# deltas = the bundle (ADR-0054: C-seq + C2a + C3 at lambda=0.01 first-
# attempt-only) + orchestration (windows-only drill at K=2, gen w=8 ||
# campaign w=16 = the 24-worker bench knee, drill-eval every 5 on
# evalset v4). Gate: standing combined paired read vs 0.5373 +/- 0.0112
# (ADR-0055, era d798917ae5).
#
# Launch checklist (the detached-run-launches memory): setsid nohup this
# script; the driver self-registers watchd and self-unregisters; ALSO arm
# a persistent log monitor (GUARD HALT / ANOMALY / battery anomalies /
# Traceback) + periodic telemetry glances. ~2h05m/iter, ~42h total.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python -m anvil.training.selfplay \
  --name d6-run14 \
  --ckpt data/training/d6-run11/iter-019/train/last.pt \
  --iterations 20 --games 480 --games-per-pair 2 \
  --workers 8 --chunk 30 --port 50063 --seed-base 20260813 \
  --temperature 1.0 --replay 4 --fresh-weight 1.0 --replay-weight 0.33 \
  --rl-workers 12 --epochs 1 --lr 1e-05 \
  --ent-weight 0.003 --ent-floor 0.08 --rl-seg 128 \
  --guard-kl 0.06 --guard-ent-mult 2.0 --guard-veto-mult 1.5 \
  --guard-casts-floor 0.8 \
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
  --seq-n 4 --seq-k 16 \
  --drill-windows-only --overlap-campaign --campaign-workers 16
