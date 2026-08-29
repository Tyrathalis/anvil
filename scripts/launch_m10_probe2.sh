#!/usr/bin/env bash
# m10-probe2 — the M10 training probe RELAUNCH after the ADR-0086 emission
# grounding surgery: does the v2 schedule surface get CONSUMED — presence
# AND content — now that decode/emission supervision is grounded in
# certified schedules?
#
# Recipe = launch_m10_probe.sh (m10-probe1) VERBATIM except the ADR-0086
# surgery pins (user-adjudicated 2026-08-29):
#   RETIRED   the own-emission dense decode CE (self-referential, degenerate
#             fixed point at empty — ADR-0085). sched_term = E/R ONLY;
#             --sched-frac 0.05 (mass-preserving: E+R's share of the old
#             0.1 bundle).
#   PROMOTED  --seedlab-frac 0.1 — the certified best-arm mint (170,
#             incl. 11 certified pure holds) is the PRIMARY (only)
#             decode/emission supervision; guard-seedlab-share 0.3,
#             guard-seedlab-spike 100x median (the ported tripline).
#   NOT BUILT empty-emission cost (would fight certified holds; the
#             ADR-0084 penalty contingency stays pinned).
#   Fresh seed base 20280829, port 50075 (collision-checked 2026-08-29
#   against every loop_config/run.json — zero hits — and live listeners).
#   No graft change: presence floor 0.012513 / content_flip 0.0 STAND.
#
# Day-zero baselines: reliance-dayzero.json (presence floor argmax_flip
# 0.012513, content_flip 0.0 EXACT, E 0.522 / R 1.800, sched_rms 0.0;
# own-emission decode CE 2.609 RETIRED with its term) + seedlab-dayzero.json
# (seedlab CE 2.730022, 170/170 — the restated FUND decode leg's base).
# Pay labels day-zero: positive CE 3.85 / auto 0.31. Holdout day-zero:
# 0/19 positives, 119/123 = 96.7% auto-correct.
#
# Pre-registered gates (ADR-0084 verbatim EXCEPT the decode leg restated at
# ADR-0086; nothing here decides FUND):
#   KILL (auto)  from accepted-iter 4: content_flip < 0.005 AND
#                (argmax_flip - 0.012513) < 0.005 AND all aux heads
#                plateaued (<2% rel. vs two accepted iterations back).
#   FUND (read)  content_flip >= 0.02 at any accepted iteration AND seedlab
#                CE <= 2.184 (0.8x day-zero 2.730 — WEAKLY discriminating,
#                probe1 hit 0.43 while degenerate; emission health rides
#                the veto) / E <= 0.470 (0.9x) / R <= 1.620 (0.9x)
#                AND guards clean AND degeneracy veto not firing.
#                PRESENCE-ONLY MOVEMENT CANNOT FUND (standing rule:
#                conditioning-surface flip gates read the content channel).
#   Degeneracy   pure-hold emission > 25% OR mean emitted length < 1.0 OR
#   veto         realized-utilization < 25%, sustained 2 accepted iters —
#                post-surgery this carries the emission-health burden of
#                FUND (nothing dense pushes live emissions any more).
#   PG-unmask    >= 4 masked accepted iters AND pay positive class-CE
#                plateau (<2%/2-iter, holdout flat) AND paymark follow >=
#                max(2x iter-0 = 0.0685, 0.05) AND holdout auto >= 85% AND
#                pay-attributed realization-failure share < 0.5 — a
#                recorded recipe event between iterations, never automatic.
#   Between      discuss-zone; the read session adjudicates.
#   Invalid-schedule penalty NOT BUILT (derived ~0, penalty-derive.json);
#   family-4 validity telemetry watches; re-derive if knowably-invalid
#   emission > 50% sustained.
#
# Riding the probe (the m10-probe1 riders carry):
#   - paymark follow iter-0 baseline recorded at launch (counts.json —
#     SIGTERM stop path fixed at ADR-0085, no rescue daemon needed);
#   - cousin/combat rates from the day-zero bridge census (cousins/cmb kv);
#   - directed-convoke capability read base = the 129-window forced family;
#   - veto-knowability v2 across the run (a read, never a guard); veto-guard
#     trips run the knowability decomposition BEFORE being treated as
#     pathology;
#   - watcher note (devlog 2026-08-28-session3): the paylabels join prints
#     its 12 known misses as FRAME ANOMALY every iteration — filter that
#     exact pattern; trip if the join summary deviates from 263/12/5.
#
# Launch checklist: setsid nohup this script; the driver self-registers
# watchd + notifies; ALSO arm the log monitor (GUARD HALT / KILL / ANOMAL /
# KL ABORT / Traceback) with a per-iteration telemetry glance.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python -m anvil.training.selfplay \
  --name m10-probe2 \
  --ckpt data/training/m10-sched-init/last.pt \
  --iterations 6 --games 480 --games-per-pair 2 \
  --workers 8 --chunk 30 --port 50075 --seed-base 20280829 \
  --temperature 1.0 --replay 4 --fresh-weight 1.0 --replay-weight 0.33 \
  --rl-workers 12 --epochs 1 --lr 1e-05 --pay-lr 1e-03 \
  --sched --sched-frac 0.05 \
  --pay-labels data/runs/payment-evalset-v2 \
  --pay-observe data/census/run-20260828-revalidation-cousins \
  --seed-labels data/runs/sched-sweep-m10/seed-sched-labels.jsonl \
  --seed-store data/trajectories/m10-ceiling-census-20260825-212414 \
  --seedlab-frac 0.1 \
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
