#!/usr/bin/env bash
# m10-probe5 — the M10 training probe on the ADR-0088 GROUNDED DRIVER with
# the ADR-0090 serve decode rule (m10-probe4 relaunch).
#
# probe4 read (ADR-0090): the FIRST post-surgery emission test answered —
# grounded supervision taught the head the label marginal in one
# iteration (seedlab per-step 2.68 -> 1.35, KL 0.010-0.015, cleanest
# loop of the three probes) and the greedy per-slot ARGMAX turned that
# calibrated marginal into a length collapse: STOP is the plurality class
# at every slot >= 1 (label marginal 17%/25%/72% at slots 1/2/3 vs ~15
# candidates splitting the rest), so emissions went 6% -> 42% -> 52%
# pure-hold, mean length 4.88 -> 1.0, utilization 5.5% — the degeneracy
# veto FIRED on two consecutive generations (pre-registered NO-FUND) with
# labels at 8% pure-hold / mean 2.45. NOT probe1's empty fixed point
# (targets are healthy); a serve-side decode defect unmasked by the first
# real supervision. Fix: sched_slot_pick — STOP only when p_stop > 0.5
# (beats all candidates combined), else argmax over candidates. Training
# (teacher-forced CE) untouched; reliance floors stand (reliance feeds
# stored schedules, never decodes); mu/loader parity holds by construction
# (the emitted schedule rides in the mu row verbatim). Day-zero emission
# counters under the new rule are read at THIS run's iteration 0 (the
# veto bars are absolute — no re-bank). Fresh name/seed 20280832/port
# 50083 (zero-hit) per ADR-0076; probe4 kept as forensic asset.
#
# Recipe = launch_m10_probe2.sh VERBATIM except the ADR-0088 pins
# (five forks user-adjudicated 2026-08-30 on the drafted leans):
#   MINT      --seed-labels/--seed-store = the sched-mint-20260830 per-era
#             certified mint (per-store comma-lists; ~3,600 windows
#             sampled from the two INIT-CKPT stores — on-distribution for
#             iteration 0 by construction; replay parity WITNESSED by
#             sched_mint.py parity before this launch).
#   MECHANICS --lab-k 4 (543-label mint at 19.2% cert rate landed under
#             the 750 bar -> the pre-adjudicated k=4 path: ~1.3 visits/
#             window/iteration, inside the <=2 rule) (one chunk per step,
#             shuffled — no step sees a fittable batch), --lab-warmup 50
#             (applied-step ramp), --seedlab-carry-w + --paylab-carry-w
#             (calibrate ONCE against the honest day-zero raw; probe1
#             grew w_seedlab 12x under per-iteration recalibration),
#             --guard-lab-memorize 0.5 armed by default (first-window
#             raw < 0.5x raw-at-calib = the probe2 impulse signature).
#   MASS      --seedlab-frac 0.05 = the retired dense term's EFFECTIVE
#             decode mass (0.1 x ~53% bundle share — the mass that drove
#             probe1's content_flip 0.0138); guard-seedlab-share 0.15
#             (the 3x-target convention follows the frac down).
#   STALENESS sched_live_ce measured grad-free every step (the retired
#             term's target pipeline as telemetry); live-gap ratio
#             sched_live_ce/seedlab_raw > 3x over two accepted
#             iterations = the mint has staled (a READ at the session,
#             never a guard; routes the online labeler by name).
#   Fresh seed base 20280830, port 50081 (collision-checked 2026-08-30,
#   zero hits incl. run.json bridge strings and live listeners).
#   No graft change: presence floor 0.012513 / content_flip 0.0 STAND.
#
# PREREQUISITES — ALL SATISFIED 2026-09-02 (~05:00):
#   1. mint finish CLEAN: 543/543 labels (653 certified positives, 110
#      dropped by the witness; cert rate 19.2% on probe states vs the
#      census 28% prior) -> the k=4 path (pre-adjudicated);
#   2. parity witness: 79.0% valid-turn survival (2,690/3,406; 288 games
#      exact, 153 sparse-flipped, 0 truncated; systematic floor 50% far
#      cleared) — salvage-by-prefix semantics, ADR-0089;
#   3. seedlab day-zero RE-BANKED: CE 2.676759 on 543/543 (zero
#      misses/unmatched; cross-validates the 170-batch's 2.730) ->
#      seedlab-dayzero-mint20260830.json; FUND decode leg <= 2.141.
#
# Pre-registered gates: ADR-0084 verbatim + the ADR-0086 restated decode
# leg on the re-banked day-zero; degeneracy veto carries emission health;
# PG-unmask conditions unchanged; presence-only movement cannot FUND.
# The emission-collapse question (open since ADR-0085) gets its first
# real test at THIS run's iteration 1 generation.
#
# Riding the probe: the probe2 riders carry verbatim (paymark iter-0
# baseline from counts.json; cousins/cmb kv; the 129-window forced-family
# capability base; veto-knowability v2 as a read; the paylabels
# FRAME-ANOMALY watcher filter, trip if join deviates from 263/12/5)
# PLUS the labs_early.json first-10 forensic dump per fixed-batch term.
#
# Launch checklist: setsid nohup this script; driver self-registers
# watchd + notifies; ALSO arm the log monitor (GUARD HALT / KILL /
# ANOMAL / KL ABORT / Traceback) with a per-iteration telemetry glance.
set -euo pipefail
cd "$(dirname "$0")/.."
MINT=data/runs/sched-mint-20260830
exec uv run python -m anvil.training.selfplay \
  --name m10-probe5 \
  --ckpt data/training/m10-sched-init/last.pt \
  --iterations 6 --games 480 --games-per-pair 2 \
  --workers 8 --chunk 30 --port 50083 --seed-base 20280832 \
  --temperature 1.0 --replay 4 --fresh-weight 1.0 --replay-weight 0.33 \
  --rl-workers 12 --epochs 1 --lr 1e-05 --pay-lr 1e-03 \
  --sched --sched-frac 0.05 \
  --pay-labels data/runs/payment-evalset-v2 \
  --pay-observe data/census/run-20260828-revalidation-cousins \
  --seed-labels "$MINT/store-m10-probe1-i000-20260828-191848/labels.jsonl,$MINT/store-m10-probe2-i000-20260829-123734/labels.jsonl" \
  --seed-store "data/trajectories/m10-probe1-i000-20260828-191848,data/trajectories/m10-probe2-i000-20260829-123734" \
  --seedlab-frac 0.05 --guard-seedlab-share 0.15 \
  --seedlab-carry-w --paylab-carry-w \
  --lab-k 4 --lab-warmup 50 \
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
