#!/usr/bin/env bash
# C-bundle smoke iteration (recipe pin 2026-08-12): ONE iteration, reduced
# sizes, full bundle machinery + overlap. Validates end-to-end: campaign ->
# label/window join -> w_seq calibration (needs >=200 trajectories: 160
# games at heur-frac 0.5 = ~240 -> 60 optimizer steps > the 50-step calib
# window) -> critic C2a aux -> train with L_seq -> battery per-iteration
# row + the gen-vs-campaign interference read (campaign_s in the monitor).
# Base args = run13 loop_config verbatim except: games/points/critic-steps
# shrunk for smoke; penalty 0.01+first (ADR-0054); workers 16 (the ADR-0032
# recipe); bundle + orchestration flags.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python -m anvil.training.selfplay \
  --name d6-bundle-smoke \
  --ckpt data/training/d6-run11/iter-019/train/last.pt \
  --iterations 1 \
  --games 160 --games-per-pair 2 --workers 16 --chunk 30 \
  --port 50063 --seed-base 20260813 --temperature 1.0 \
  --replay 4 --fresh-weight 1.0 --replay-weight 0.33 \
  --rl-workers 12 --epochs 1 --lr 1e-05 \
  --ent-weight 0.003 --ent-floor 0.08 --rl-seg 128 \
  --guard-kl 0.06 --guard-ent-mult 2.0 --guard-veto-mult 1.5 \
  --guard-casts-floor 0.8 \
  --penalty 0.01 --penalty-grouping first \
  --heur-frac 0.5 \
  --critic data/training/d6-run11/iter-019/critic/last.pt \
  --critic-lr 1e-05 --critic-steps 500 --critic-batch 256 \
  --value-weight 0.5 --traj-per-step 4 --reask \
  --drill-selection data/runs/drill-selection-v5/selection.jsonl \
  --drill-points-per-iter 20 --drill-k 2 \
  --drill-replay-ckpt data/training/d6-run11/iter-019/train/last.pt \
  --seq-n 4 --seq-k 16 \
  --drill-windows-only --overlap-campaign
