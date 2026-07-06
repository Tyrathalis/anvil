#!/bin/sh
# M1 D3 pilot corpus: 50K games over pool cf2ca6ba, obs+CastPlan labels on,
# personalities randomized, heuristic self-play (nothing bridged).
# Detached + nice-19 per the ledgered conventions; pause any time with
#   uv run python -m anvil.bridge.harness pause data/runs/d3pilot-*
# and continue with `resume` (games are seed-pinned; chunks re-issue cleanly).
cd /home/tyrathalis/Everything/Projects/Anvil || exit 1
setsid nohup uv run python -m anvil.bridge.harness launch \
  --pool --games 50000 --games-per-pair 5 \
  --workers 16 --chunk 200 \
  --bridge local-random --tags none \
  --purpose d3pilot --obs \
  > data/runs/d3pilot-launch.log 2>&1 &
echo "d3pilot launched detached (pid $!); log: data/runs/d3pilot-launch.log"
