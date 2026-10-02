#!/usr/bin/env bash
# The settings pass, fourth chain (10-01 22:50): the ADR-0119 ladder's RUNG 2 RERUN after the first
# cell (settings-pass3) halted at iteration 3 on the kl guard. The attribution replays
# (data/runs/rung2-attrib/read.md) put the halt in the optimizer's trunk step once the value gradients
# left the trunk: --trunk-lr 3e-6 alone restores the control's kl_mu (0.0020 vs 0.0024; as run 0.0195),
# --value-head-lr 1e-4 moves the detached head's bias (v0 0.60 -> 0.55 in iteration 0) without touching
# kl_mu. One cell from day-zero, 30 h, the same bar (Spearman within one SE of 0.374 across the cell;
# network-alone not worse than the fresh alloc 0.5394 +/- 0.0070 by the -1.0pp margin on a fresh paired
# read, seed base 20261001 — the chain's own 2,000-game read at the close is a first look, not the number).
# Launch (the box quiet, main at the rerun commit):
#   uv run python -m anvil.runs launch --name settings-pass4 --dir data/runs/settings-pass4 --resume-on-gone \
#     --watch 'data/training/settings-*' --watch 'data/runs/settings-*' --watch 'data/runs/sp*' \
#     --stall-min 180 -- bash scripts/settings_pass_chain4.sh
set -u
export CHAIN_OUT=${CHAIN_OUT:-settings-pass4}
export ANCHOR_WEIGHT=${ANCHOR_WEIGHT:-0.1}
export ARMS=${ARMS:-stopgrad-t3e6}
exec bash "$(dirname "$0")/settings_pass_chain.sh"
