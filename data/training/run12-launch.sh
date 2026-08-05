#!/bin/sh
# d6-run12 = the M5 D2 compounding run (ADR-0034). run11 recipe VERBATIM
# except the forced deltas: name, init/critic/mainline pin = run11/iter-019,
# drill-selection-v3, w=16 (ADR-0032; chunk 30 stays the ceiling, per-batch
# clamp in the driver), fresh seed base, + the standing mid-run drill-eval
# phase (evalset v3, iters 9/19).
cd /home/tyrathalis/Everything/Projects/Anvil
mkdir -p data/training/d6-run12
exec nice -n 19 .venv/bin/python -m anvil.training.selfplay \
  --name d6-run12 \
  --ckpt data/training/d6-run11/iter-019/train/last.pt \
  --iterations 20 --games 480 --games-per-pair 2 --workers 16 --chunk 30 \
  --port 50063 --seed-base 20260804 --temperature 1.0 \
  --replay 4 --fresh-weight 1.0 --replay-weight 0.33 --rl-workers 12 \
  --epochs 1 --lr 1e-5 --ent-weight 0.003 --ent-floor 0.08 --rl-seg 128 \
  --guard-kl 0.06 --guard-ent-mult 2.0 --guard-veto-mult 1.5 \
  --guard-casts-floor 0.8 \
  --penalty 0.02 --heur-frac 0.5 \
  --critic data/training/d6-run11/iter-019/critic/last.pt \
  --critic-lr 1e-5 --critic-steps 2000 --critic-batch 256 \
  --value-weight 0.5 --traj-per-step 4 \
  --arms-every 5 --arms-pairs data/runs/d5arm-d0-s0-20260714-143546/pairs.txt \
  --arms-games 200 --arms-seed-base 20260710 \
  --drill-selection data/runs/drill-selection-v3/selection.jsonl \
  --drill-points-per-iter 15 --drill-k 8 \
  --drill-replay-ckpt data/training/d6-run11/iter-019/train/last.pt \
  --drill-eval-set data/runs/drill-evalset-v3 --drill-eval-every 10 \
  --reask \
  > data/training/d6-run12/launch.log 2>&1
