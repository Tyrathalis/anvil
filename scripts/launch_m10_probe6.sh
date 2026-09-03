#!/usr/bin/env bash
# m10-probe6 — the M10 training probe with the ADR-0092 CONSUMER COUPLING
# (probe5 relaunch): two supervisions for two competencies.
#
#   FOLLOW    --follow-frac 0.05 (+carry-w, share guard 0.15): feed-and-follow
#             CE on the priority pointer at the mint's certified windows with
#             the certified arm FED (consumption, not BC; certified rows only).
#             Follow window = the natural line's POST-LAND window (the arm
#             executor is land-first; day-zero diagnostic: at the emission
#             window CE 16.6 with argmax=land on 130/134 land-available
#             windows). Day-zero banked at the init ckpt: follow CE
#             10.485799 on 496 windows (follow-dayzero-20260902.json) ->
#             FUND follow leg <= 8.39.
#   EMITTER   --seed-labels = labels-full.jsonl (schedule EVERY turn: 543
#             certified + 2,126 natural-line witnessed casts + holds where
#             natural held; 2,157 join at the window, 512 unmatched dropped).
#             Day-zero re-banked: seedlab CE 2.662957 on 2,157 ->
#             FUND decode leg <= 2.130 (seedlab-dayzero-full20260902.json).
#   READ      ADR-0084 verbatim; FUND = content_flip >= 0.02 on the fixed
#             reliance population (PRIMARY) AND utilization >= 25% as a FLOOR
#             (inflates on natural-line windows) AND aux legs under bars
#             (seedlab <= 2.130; follow <= 0.8x its day-zero) AND guards
#             clean AND veto not firing. Veto axes ABSOLUTE (unchanged).
#   GUARDS    memorize guard reads the iteration MEDIAN of windowed per-step
#             raws (probe5 paylab artifact); KL 0.06 is the tripline for a
#             third fixed-batch term (paylab -> 0.05 is the routed response).
#   TEARDOWN  worker JVMs now die with the harness (PR_SET_PDEATHSIG) — no
#             orphans on halt/SIGTERM.
#   SMOKE-AXES DECLARED: the follow term is unit-tested (batch synthesis,
#             guards) and day-zero-banked but NOT smoke-tested inside a live
#             loop iteration; iteration 0's labs_early.json (follow) +
#             follow_calibration.json raw vs its day-zero carry that burden.
#   Fresh seed base 20280833, port 50084 (zero-hit) per ADR-0076; probe5
#   kept as forensic asset.
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
  --name m10-probe6 \
  --ckpt data/training/m10-sched-init/last.pt \
  --iterations 6 --games 480 --games-per-pair 2 \
  --workers 8 --chunk 30 --port 50084 --seed-base 20280833 \
  --temperature 1.0 --replay 4 --fresh-weight 1.0 --replay-weight 0.33 \
  --rl-workers 12 --epochs 1 --lr 1e-05 --pay-lr 1e-03 \
  --sched --sched-frac 0.05 \
  --pay-labels data/runs/payment-evalset-v2 \
  --pay-observe data/census/run-20260828-revalidation-cousins \
  --seed-labels "$MINT/store-m10-probe1-i000-20260828-191848/labels-full.jsonl,$MINT/store-m10-probe2-i000-20260829-123734/labels-full.jsonl" \
  --seed-store "data/trajectories/m10-probe1-i000-20260828-191848,data/trajectories/m10-probe2-i000-20260829-123734" \
  --seedlab-frac 0.05 --guard-seedlab-share 0.15 \
  --seedlab-carry-w --paylab-carry-w \
  --follow-frac 0.05 --follow-carry-w --guard-follow-share 0.15 \
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
