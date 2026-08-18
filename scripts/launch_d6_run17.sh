#!/usr/bin/env bash
# d6-run17 — the M8 D2' run: critic-ordered curation (the ADR-0061 funded
# branch; the never-run method with the audit gate PASSED at 0.4205).
# Recipe = run13's loop_config verbatim (the run11 recipe: same guards,
# in-loop critic unchanged, arms cadence, drill-campaign shape,
# 15 points/iter x K=8 rotation) EXCEPT:
#   - drill selection = drill-selection-m8-critic (320 entries at 3.9x
#     selectivity from the 1,253-candidate 4x pool, a2 quotas 18.75%
#     ahead, critic-ordered within bands)
#   - Sec.6c pricing = the STANDING corrected pricing (0.01 / grouping
#     'first'), NOT run13's superseded 0.02/event. User decision
#     2026-08-18: 'verbatim' binds the recipe's structure for
#     comparability, not a measured-defective reward term (ADR-0054
#     keeps event pricing for era reproduction only; run13's veto
#     elevation 0.215 was its documented cost). Delta vs run13 is
#     therefore curation + pricing; the gate of record is vs the
#     0.5373 baseline, unaffected.
#   - drill-eval instrumentation: evalset-v4 every 5 iters (recipe-
#     neutral, the M7 carry)
#   - fresh seed base 20260821
# Gate: standing 2,000-game combined paired read vs 0.5373 +/- 0.0112
# + evalset-v4 decomposition + battery. ~1h/iter (run13 precedent).
#
# Launch checklist: setsid nohup this script; the driver self-registers
# watchd + holds the sleep inhibitor + notifies; ALSO arm the log
# monitor (GUARD HALT / ANOMAL / KL ABORT / Traceback) with 2h
# telemetry-glance heartbeat.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python -m anvil.training.selfplay \
  --name d6-run17 \
  --ckpt data/training/d6-run11/iter-019/train/last.pt \
  --iterations 20 --games 480 --games-per-pair 2 \
  --workers 8 --chunk 30 --port 50063 --seed-base 20260821 \
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
  --drill-selection data/runs/drill-selection-m8-critic/selection.jsonl \
  --drill-points-per-iter 15 --drill-k 8 \
  --drill-replay-ckpt data/training/d6-run11/iter-019/train/last.pt \
  --drill-eval-set data/runs/drill-evalset-v4 --drill-eval-every 5
