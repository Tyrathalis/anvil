#!/usr/bin/env bash
# The settings pass, third chain (10-01): the ADR-0119 ladder's RUNG 2, to run ONLY if the rung 1'
# resolution read misses its fixed margin (anchor-w01 - alloc >= -1.0pp). One cell from day-zero,
# 30 h, the same bar: the alloc arm's recipe + the value anchor at weight 0.1 as a HEAD-ONLY term +
# --value-stopgrad-trunk (model.py value_stopgrad: the value head reads a detached [STATE] read-out,
# so V-trace, the anchor and the distill carry's value BCE train the head alone; the trunk is the
# policy's; gn_v / gn_anchor read 0). Pre-registered 10-01 before the resolution read landed.
# Launch (the box quiet, main at the rung-2 commit):
#   uv run python -m anvil.runs launch --name settings-pass3 --dir data/runs/settings-pass3 --resume-on-gone \
#     --watch 'data/training/settings-*' --watch 'data/runs/settings-*' --watch 'data/runs/sp*' \
#     --stall-min 180 -- bash scripts/settings_pass_chain3.sh
set -u
export CHAIN_OUT=${CHAIN_OUT:-settings-pass3}
export ANCHOR_WEIGHT=${ANCHOR_WEIGHT:-0.1}
export ARMS=${ARMS:-stopgrad}
exec bash "$(dirname "$0")/settings_pass_chain.sh"
