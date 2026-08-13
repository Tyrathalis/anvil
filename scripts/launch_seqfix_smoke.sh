#!/usr/bin/env bash
# ADR-0056 validation smoke: TWO iterations (the run14 failure signature was
# CROSS-ITERATION seq_raw growth — a 1-iteration smoke cannot certify the
# fix). Base = launch_bundle_smoke.sh verbatim + the ADR-0056 deltas
# (defaults made explicit: --seq-margin 6.0 hinge, --guard-seq-share 0.3;
# rl.py gets --kl-abort 0.3 = 5x guard-kl from the driver automatically).
# Pass criteria: seq_share ~0.1 and flat across the iteration boundary,
# |seq_raw| bounded (no monotonic growth), w_seq carried at iter 1, guards
# quiet, join >= ~18/20.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python -m anvil.training.selfplay \
  --name d6-seqfix-smoke \
  --ckpt data/training/d6-run11/iter-019/train/last.pt \
  --iterations 2 \
  --games 160 --games-per-pair 2 --workers 16 --chunk 30 \
  --port 50063 --seed-base 20260814 --temperature 1.0 \
  --replay 4 --fresh-weight 1.0 --replay-weight 0.33 \
  --rl-workers 12 --epochs 1 --lr 1e-05 \
  --ent-weight 0.003 --ent-floor 0.08 --rl-seg 128 \
  --guard-kl 0.06 --guard-ent-mult 2.0 --guard-veto-mult 1.5 \
  --guard-casts-floor 0.8 --guard-seq-share 0.3 \
  --penalty 0.01 --penalty-grouping first \
  --heur-frac 0.5 \
  --critic data/training/d6-run11/iter-019/critic/last.pt \
  --critic-lr 1e-05 --critic-steps 500 --critic-batch 256 \
  --value-weight 0.5 --traj-per-step 4 --reask \
  --drill-selection data/runs/drill-selection-v5/selection.jsonl \
  --drill-points-per-iter 20 --drill-k 2 \
  --drill-replay-ckpt data/training/d6-run11/iter-019/train/last.pt \
  --seq-n 4 --seq-k 16 --seq-margin 6.0 \
  --drill-windows-only --overlap-campaign
