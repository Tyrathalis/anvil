#!/usr/bin/env bash
# d6-run20 — the M9 D6 plan-latent probe: does a detached-carry turn-plan
# latent with dense joint aux supervision get CONSUMED by the policy?
#
# Recipe = d6-run18's loop_config (the run11 lineage) EXCEPT the D6 spec
# pins (m9-d6-plan-latent-spec, recipe session 2026-08-25):
#   init      data/training/d6-plan-init/last.pt — iter-019 grafted with the
#             plan params at design init (proj rms 0.0 verified) and the
#             pay_ params STRIPPED (ADR-0073: infrastructure routing; the
#             serve pay tag is never advertised, attribution stays
#             pure-latent). NO --pay-lr (no pay params to group).
#   --plan    serve carry active (carry_plan gates on the graft), loop
#             pass-0 + joint aux (ADR-0074), reliance readout per accepted
#             iteration on the pinned fixed store, KILL SIGNAL armed from
#             accepted-iteration 4 (spec §7 numerics; exit 4 + PLAN-KILL).
#   --plan-lr 1e-3 for the aux HEADS (trunk 1e-5); --plan-proj-lr 1e-4 for
#             the consumption proj (iter-0 amendment: the proj gets dense
#             PG at every carried window — at 1e-3 the policy left the
#             behavior policy at ~100x recipe speed and the kl guard bound
#             at iteration 0 with kl 0.07 BEFORE the aux even activated;
#             flip was already 2.6% and aux BCE 1.79->0.29 in that one
#             iteration, so the channel needs no starvation compensation).
#   --plan-frac 0.1, per-iteration recalibration (ADR-0057 default; no
#             --plan-carry-w).
#   8 x 480, no arms, no drill campaign, no payment drill scoring.
#   Guards unchanged + plan_share 0.3 (the seq-share twin).
#   Fresh seed base 20270825 (checked against loop_state/run.json bases).
#
# Day-zero baselines banked (data/training/d6-plan-init/reliance-dayzero.json):
# reliance_l1 0.0 / argmax_flip 0.0 EXACT (live bit-identity, 10,629 carried
# windows), aux_act_bce 0.7105, aux_delta_l1 0.638.
#
# Pre-registered gates (spec §7, nothing here decides FUND):
#   KILL (auto)  from accepted-iter 4: max argmax_flip < 0.005 AND aux BCE
#                plateaued (<2% rel. vs two accepted iterations back).
#   FUND (read)  argmax_flip >= 0.02 at any accepted iteration, guards
#                clean, aux_act_bce <= 0.568 (0.8x day-zero).
#   Between      discuss-zone; the read session adjudicates.
#
# Iteration-1 amendment (user-approved 2026-08-25): veto-mult 1.5 -> 2.5 FOR
# THIS PROBE. The latent's first consumed behavior is amplified knowable-veto
# probing (i0->i1: first-attempt mana-relevant vetoes 1,381 -> 2,838,
# knowable fraction 0.559 -> 0.615, generic_short +165% — the ADR-0062
# interface artifact through the new channel at 10x historical speed). The
# probe gates are orthogonal to veto rate; FUND's guards-clean clause reads
# against THIS amended set; the veto trajectory under the latent is a
# first-class secondary read for the closeout.
#
# Launch checklist: setsid nohup this script; the driver self-registers
# watchd + notifies; ALSO arm the log monitor (GUARD HALT / PLAN KILL /
# ANOMAL / KL ABORT / Traceback) with a 2h telemetry glance.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python -m anvil.training.selfplay \
  --name d6-run20 \
  --ckpt data/training/d6-plan-init/last.pt \
  --iterations 8 --games 480 --games-per-pair 2 \
  --workers 8 --chunk 30 --port 50067 --seed-base 20270825 \
  --temperature 1.0 --replay 4 --fresh-weight 1.0 --replay-weight 0.33 \
  --rl-workers 12 --epochs 1 --lr 1e-05 \
  --plan --plan-lr 1e-03 --plan-proj-lr 1e-04 --plan-frac 0.1 \
  --ent-weight 0.003 --ent-floor 0.08 --rl-seg 128 \
  --guard-kl 0.06 --guard-ent-mult 2.0 --guard-veto-mult 2.5 \
  --guard-casts-floor 0.8 --guard-plan-share 0.3 \
  --penalty 0.01 --penalty-grouping first --heur-frac 0.5 \
  --critic data/training/d6-run11/iter-019/critic/last.pt \
  --critic-lr 1e-05 --critic-steps 2000 --critic-batch 256 \
  --value-weight 0.5 --traj-per-step 4 --reask \
  --arms-every 0
