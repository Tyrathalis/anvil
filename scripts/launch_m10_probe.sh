#!/usr/bin/env bash
# m10-probe1 — the M10 training probe (D4-shape, ~5 accepted iterations):
# does the v2 schedule surface get CONSUMED — presence AND content — with
# the R5 label stack feeding the masked pay head?
#
# Recipe = d6-run20's loop_config (the run11 lineage) EXCEPT the M10 pins
# (m10-build-spec R1-R6; numerics ADR-0084, user-adjudicated 2026-08-28;
# leans re-approved at launch 2026-08-28):
#   init      data/training/m10-sched-init/last.pt — iter-019 grafted with
#             the sched slot tokens + decode/E/R heads + the M9 pay surface
#             restored (pay_bias/pay_kind_emb 8 kinds/pointer, +2.0 auto
#             init) + pay_mark_emb (cand_paymark, live-but-untrained).
#   --sched   serve carry (revise-on-trigger) + decode/E/R aux + PG staged
#             pay mask from birth; sched-lr 1e-3 / sched-proj-lr 1e-4
#             (defaults; the run20 iter-0 class absorbed as a pin, NO
#             starvation compensation on the input proj) / sched-frac 0.1 /
#             guard-sched-share 0.3; reliance readout per accepted
#             iteration on the pinned m10-reliance-pop-20260827 (default).
#   --pay-lr  1e-3 — pay params ride the M9 group (build-spec §2).
#   labels    --pay-labels payment-evalset-v2 at the cousins-jar observe
#             frames (run-20260828-revalidation-cousins, 263/280 joined,
#             ADR-0084) = the pay head's ONLY signal under the mask;
#             --seed-labels sched-sweep-m10 best-arm mint (170) against
#             the ceiling census store, frac 0.05 (enrichment).
#   scoring   --pay-drill-dir run-20260828-holdout-observe-cousins (the
#             pre-registered conditional holdout, 142 frames, NEVER
#             ingested) scored every accepted iteration, ckpt's own embed.
#   6 x 480 (6 attempted buys ~5 accepted with one guard-reject margin),
#   no arms, no drill campaign. Guards run20-verbatim incl veto-mult 2.5
#   (the run20 iteration-1 amendment, standing since).
#   Fresh seed base 20280828, port 50070 (both collision-checked against
#   every loop_config/run.json 2026-08-28).
#
# Day-zero baselines banked (m10-sched-init/reliance-dayzero.json, re-banked
# IDENTICAL post-cousins): presence floor argmax_flip 0.012513, content_flip
# 0.0 EXACT, decode CE 2.609 / E 0.522 / R 1.800, sched_rms 0.0. Pay labels
# day-zero: positive CE 3.85 / auto 0.31. Holdout day-zero: 0/19 positives,
# 119/123 = 96.7% auto-correct (the +2.0-bias point).
#
# Pre-registered gates (ADR-0084 + m10-probe-numerics-draft = the statement
# of record; nothing here decides FUND):
#   KILL (auto)  from accepted-iter 4: content_flip < 0.005 AND
#                (argmax_flip - 0.012513) < 0.005 AND all four aux heads
#                plateaued (<2% rel. vs two accepted iterations back).
#   FUND (read)  content_flip >= 0.02 at any accepted iteration AND decode
#                CE <= 2.087 (0.8x) / E <= 0.470 (0.9x) / R <= 1.620 (0.9x)
#                AND guards clean AND degeneracy veto not firing.
#                PRESENCE-ONLY MOVEMENT CANNOT FUND (standing rule:
#                conditioning-surface flip gates read the content channel).
#   Degeneracy   pure-hold emission > 25% OR mean emitted length < 1.0 OR
#   veto         realized-utilization < 25%, sustained 2 accepted iters.
#   PG-unmask    >= 4 masked accepted iters AND pay positive class-CE
#                plateau (<2%/2-iter, holdout flat) AND paymark follow >=
#                max(2x iter-0, 0.05) AND holdout auto >= 85% AND
#                pay-attributed realization-failure share < 0.5 — a
#                recorded recipe event between iterations, never automatic.
#   Between      discuss-zone; the read session adjudicates.
#   Invalid-schedule penalty NOT BUILT (derived ~0, penalty-derive.json);
#   family-4 validity telemetry watches; re-derive if knowably-invalid
#   emission > 50% sustained.
#
# Riding the probe (launch riders, devlog 2026-08-28-session2):
#   - paymark follow iter-0 baseline recorded at launch (counts.json);
#   - cousin/combat rates from the day-zero bridge census (cousins/cmb kv);
#   - directed-convoke capability read base = the 129-window forced family;
#   - veto-knowability v2 across the run (probing-dissolution secondary
#     read — a read, never a guard); veto-guard trips run the knowability
#     decomposition BEFORE being treated as pathology.
#
# Launch checklist: setsid nohup this script; the driver self-registers
# watchd + notifies; ALSO arm the log monitor (GUARD HALT / KILL / ANOMAL /
# KL ABORT / Traceback) with a per-iteration telemetry glance.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python -m anvil.training.selfplay \
  --name m10-probe1 \
  --ckpt data/training/m10-sched-init/last.pt \
  --iterations 6 --games 480 --games-per-pair 2 \
  --workers 8 --chunk 30 --port 50070 --seed-base 20280828 \
  --temperature 1.0 --replay 4 --fresh-weight 1.0 --replay-weight 0.33 \
  --rl-workers 12 --epochs 1 --lr 1e-05 --pay-lr 1e-03 \
  --sched \
  --pay-labels data/runs/payment-evalset-v2 \
  --pay-observe data/census/run-20260828-revalidation-cousins \
  --seed-labels data/runs/sched-sweep-m10/seed-sched-labels.jsonl \
  --seed-store data/trajectories/m10-ceiling-census-20260825-212414 \
  --ent-weight 0.003 --ent-floor 0.08 --rl-seg 128 \
  --guard-kl 0.06 --guard-ent-mult 2.0 --guard-veto-mult 2.5 \
  --guard-casts-floor 0.8 \
  --penalty 0.01 --penalty-grouping first --heur-frac 0.5 \
  --critic data/training/d6-run11/iter-019/critic/last.pt \
  --critic-lr 1e-05 --critic-steps 2000 --critic-batch 256 \
  --value-weight 0.5 --traj-per-step 4 --reask \
  --arms-every 0 \
  --pay-drill-dir data/census/run-20260828-holdout-observe-cousins \
  --pay-drill-embed data/embeddings/cf2ca6ba-qwen3
