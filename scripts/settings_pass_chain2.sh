#!/usr/bin/env bash
# The settings pass, second chain (09-29): the ADR-0119 ladder's rung 1' after the anchor cell's close
# (0.4895 +/- 0.0112: the anchor at weight 0.5 costs strength; gn_anchor ~10-20x gn_pg on the trunk).
# One cell, the anchor cell's recipe with --anchor-weight 0.1 (value weight unchanged), the same bar.
# Launch AFTER settings-pass writes DONE:
#   uv run python -m anvil.runs launch --name settings-pass2 --dir data/runs/settings-pass2 --resume-on-gone \
#     --watch 'data/training/settings-*' --watch 'data/runs/settings-*' --watch 'data/runs/sp*' \
#     --stall-min 180 -- bash scripts/settings_pass_chain2.sh
set -u
export CHAIN_OUT=${CHAIN_OUT:-settings-pass2}
export ANCHOR_WEIGHT=${ANCHOR_WEIGHT:-0.1}
export ARMS=${ARMS:-anchor-w01}
exec bash "$(dirname "$0")/settings_pass_chain.sh"
