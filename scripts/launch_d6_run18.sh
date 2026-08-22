#!/usr/bin/env bash
# d6-run18 — the M9 D4 learning-signal probe: does the §3c payment head
# learn anything the auto-payer structurally lacks?
#
# Recipe = run17's loop_config (the run11 lineage: guards, in-loop critic,
# §6c pricing, mixed opponents, replay shape) EXCEPT the D4 recipe pins
# (m9-plan.md "D4 run recipe", 2026-08-21):
#   pin 1  init = data/training/d4-init/last.pt — iter-019 GRAFTED with the
#          pay_ params (scripts/graft_pay_init.py). Ungrafted, the server
#          gates the payment tag off (has_pay) and iteration 0 bridges ZERO
#          payment windows. Verified: the grafted ckpt reproduces the banked
#          post-boundary day-zero scores EXACTLY (positive 2/64, auto-correct
#          196/214).
#   pin 2  --pay-lr 1e-3 (trunk stays 1e-5). The loop takes ~417 optimizer
#          steps/iteration, so at trunk lr the fresh head displaces <=0.03
#          across the whole run: a false clean negative on the branch that
#          retires the formulation. No lr sweep (pin 3) — bought with
#          head-movement instrumentation instead.
#   pin 4  8 iterations x 480 games (~30 min/iter measured from run17
#          checkpoint mtimes => ~4-4.5h). The gate reads at ANY accepted
#          iteration and drill scoring is offline, so extra iterations cost
#          only wall-clock.
#   pin 5  NO drill campaign — the standing selection asset is pre-boundary
#          AND payment-agnostic. Escalation if iter-0/1 deviation telemetry
#          reads starved: payment-targeted forks (recorded in the plan).
#   pin 7  --pay-drill-dir = the post-boundary revalidation observe frames;
#          every iteration's produced ckpt is scored against the pinned gate,
#          live in analysis.md.
#   pin 8  arms + evalset-v4 drill-eval DROPPED (no strength claim at D4;
#          both return at D5). This is where pin 4's wall-clock comes from.
#   pin 11 fresh seed base 20261101 (checked against every run.json).
#
# Pre-registered gate (m9-plan D4, PINNED 2026-08-21 — nothing here decides
# it; the read session adjudicates):
#   FUND ⇒ D5      positive-drill argmax accuracy >= 7/64 at any accepted
#                  iteration WITH auto-correct >= 182/214 same-iteration.
#   CLEAN NEGATIVE argmax deviation < 2% (always-auto collapse) AND positive
#                  <= 4/64 across the probe.
#   Between        discuss-zone; recorded, nothing auto-promotes.
# Baselines: drills = 2/64 and 196/214 (post-boundary re-banked); live
# pay_deviation = this run's own iter-0 (recorded into loop_state baseline).
#
# Guards unchanged. Recorded reading (pin 9): the veto guard is a CEILING and
# M9 predicts vetoes FALL, so it should not bind; --guard-casts-floor 0.8 is
# the one that could halt on the very mechanism the probe exists to observe —
# if it fires, that is a READ, not just a halt.
#
# Launch checklist: setsid nohup this script; the driver self-registers
# watchd + holds the sleep inhibitor + notifies; ALSO arm the log monitor
# (GUARD HALT / ANOMAL / KL ABORT / Traceback) with a 2h telemetry glance.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python -m anvil.training.selfplay \
  --name d6-run18 \
  --ckpt data/training/d4-init/last.pt \
  --iterations 8 --games 480 --games-per-pair 2 \
  --workers 8 --chunk 30 --port 50067 --seed-base 20261101 \
  --temperature 1.0 --replay 4 --fresh-weight 1.0 --replay-weight 0.33 \
  --rl-workers 12 --epochs 1 --lr 1e-05 --pay-lr 1e-03 \
  --ent-weight 0.003 --ent-floor 0.08 --rl-seg 128 \
  --guard-kl 0.06 --guard-ent-mult 2.0 --guard-veto-mult 1.5 \
  --guard-casts-floor 0.8 \
  --penalty 0.01 --penalty-grouping first --heur-frac 0.5 \
  --critic data/training/d6-run11/iter-019/critic/last.pt \
  --critic-lr 1e-05 --critic-steps 2000 --critic-batch 256 \
  --value-weight 0.5 --traj-per-step 4 --reask \
  --arms-every 0 \
  --pay-drill-dir data/census/run-20260821-revalidation \
  --pay-drill-embed data/embeddings/cf2ca6ba-qwen3
