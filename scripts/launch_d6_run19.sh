#!/usr/bin/env bash
# d6-run19 — the M9 D4 CONTROL run (ADR-0069 routing, user-approved
# 2026-08-22): does the §3c payment surface hold the veto channel flat
# under the condition that made it run away?
#
# Why this run exists. D4's pre-registered signal 2 (the knowable-veto
# trajectory) went unread until the read session, and when read it could
# not be attributed: d6-run18's kvr fell 33% (0.0635 -> 0.0425, CIs
# separated, slope -0.0076/iter at t=-7.55, the steepest in the ledger)
# BUT the ledger splits perfectly by drill-campaign status —
#
#   drill-fed   run11 +0.00073  run13 -0.00295  run16 +0.00355  run17 +0.00097
#   drill-free  run7b -0.00435  run8  +0.00026  run9  -0.00594  run18 -0.00762
#
# — and D4's recipe pinned `drill_selection: None`. The decline also
# carries no affordability signature (knowable:timing, untouchable by
# §3c, fell -51.6%, MORE than colors_short -24.6% / generic_short
# -35.4%). So ADR-0062's collapse prediction is UNTESTED, not falsified.
#
# This run restores the campaign and changes nothing else. run18 verbatim
# + a drill campaign, same 8x480 shape, same init, same guards.
#
# THE READ (state it before the data exists): the veto-rate slope over
# i0-i7, against run18's -0.00762 (drill-free, §3c on) and the drill-fed
# family's +0.0007..+0.0036 (§3c off). Plus kvr at i000/i007 through the
# ADR-0063 v2 instrument, and the taxonomy split (a REAL §3c collapse is
# concentrated in colors_short/generic_short and spares knowable:timing;
# that is the discriminator run18 failed).
#   §3c HOLDS THE CHANNEL   slope <= 0 over i0-i7 with the campaign
#                           present, i.e.
#                           clearly outside the drill-fed family, AND the
#                           decline concentrated in the mana categories.
#   §3c DOES NOTHING        slope back in the drill-fed band (+0.001..
#                           +0.004) => run18's decline was the missing
#                           campaign, ADR-0062's prediction falsified for
#                           this surface, and the §3a second act takes the
#                           slot with the payment surface held as
#                           infrastructure.
#   Between                 discuss; nothing auto-promotes (D4's lesson).
# TWO READS, one run (12 iterations, user decision 2026-08-22):
#   (a) THE MATCHED SLOPE, i0-i7 — the window run18 ran, so the campaign
#       is the only delta. This is the primary read above.
#   (b) THE TAIL, i8-i11 — the window where the runaway actually lives.
#       run16 and run17 were both quiet through iteration 9 and halted at
#       16 and 11; 8 iterations would have stopped just short of the only
#       place the veto guard has ever fired. If the guard halts here, that
#       is a READ (§3c does not buy stability), not a failed run. If it
#       does NOT halt where run17 did, that is the stability claim getting
#       its first positive evidence — still one run, still not proof.
#   The tail is the half that cannot be recovered later without paying for
#   the whole run again, which is why it is bought up front.
#
# Deltas vs d6-run18 (scripts/launch_d6_run18.sh) — campaign only:
#   --drill-selection  data/runs/drill-selection-m9control/selection.jsonl
#                      Regenerated IN-ERA (user decision 2026-08-22).
#                      run17's drill-selection-m8-critic CANNOT be reused:
#                      the campaign re-simulates each entry from its seed
#                      on the CURRENT jar (grindstone plan --anchor
#                      selected -> generate), and the boundary moved the
#                      engine (forkcheck 10.0%), so pre-boundary curated
#                      turns land in different games. Selection assets are
#                      ckpt-era-scoped (standing rule).
#                      Stock is FRESHLY GENERATED, not borrowed: every
#                      post-boundary store on disk is either gate-seeded
#                      (m9-rebaselinearm runs at seed_base 20260710 — the
#                      final_read default; forking training drills from
#                      those positions would contaminate D5's own strength
#                      read) or too small (run18's vs-heuristic arms are
#                      120 games/iteration and sampled, not argmax).
#   --drill-points-per-iter 15 --drill-k 8   run17's campaign shape.
#   --drill-replay-ckpt d6-run11/iter-019/train/last.pt   the UNGRAFTED
#                      policy that generated the stock — the mainline must
#                      replay under the policy whose losses were curated.
#                      d4-init would diverge (its +2.0 payment head moves
#                      argmax on 8.6% of payment windows at day zero).
#   --seed-base 20261215, --port 50068       fresh, collision-checked
#                      against every run.json (pin 11).
# Everything else is run18's line verbatim, including the D4 pins:
#   init = d4-init (grafted; ungrafted bridges ZERO payment windows at
#   iter-0), --pay-lr 1e-3, --arms-every 0, no drill-eval set, the pinned
#   pay-drill-dir so every accepted iteration still scores the capability
#   curve for free.
#
# Guards unchanged and now load-bearing in BOTH directions: the veto guard
# (1.5x iter-0) is the runaway tripwire this run is trying to provoke or
# prevent. If it halts, that is THE READ, not a failure.
#
# Wall clock: ~35-45 min/iteration with the campaign (run18 was ~20 min
# campaign-free; run17 carried ~1,000 extra trajectories/iteration) =>
# ~7-9h for 12 iterations. Overnight by design (user, 2026-08-22).
#
# Launch checklist: setsid nohup this script; the driver self-registers
# watchd + holds the sleep inhibitor + notifies; ALSO arm the log monitor
# (GUARD HALT / ANOMAL / KL ABORT / Traceback) with a telemetry glance.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python -m anvil.training.selfplay \
  --name d6-run19 \
  --ckpt data/training/d4-init/last.pt \
  --iterations 12 --games 480 --games-per-pair 2 \
  --workers 8 --chunk 30 --port 50068 --seed-base 20261215 \
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
  --drill-selection data/runs/drill-selection-m9control/selection.jsonl \
  --drill-points-per-iter 15 --drill-k 8 \
  --drill-replay-ckpt data/training/d6-run11/iter-019/train/last.pt \
  --pay-drill-dir data/census/run-20260821-revalidation \
  --pay-drill-embed data/embeddings/cf2ca6ba-qwen3
