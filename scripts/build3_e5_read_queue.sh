#!/usr/bin/env bash
# Evening 5 (ADR-0106 A6): the 600-game paired read queued behind the calibration
# chain (the box) and a GO marker (the forkcheck compare read by hand):
#   on  = today's served set (e3 ckpt: six surfaces + tuck) under the search recipe
#         (rate 1, rolls 2, surf 2, bar 0.10, T 0.025) — the shakedown's recipe minus surface acting
#   act = the same + -searchactkinds mode (mainline surface acting on modes)
# Pre-registered (ADR-0106 A6): act within one SE of on → the gate retires on searched windows;
# a clear negative → the value head on modes is not yet trustworthy, the gate stays until the loop.
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=data/runs/build3-surface-read-b3e5
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "queued: waiting for data/runs/build3-priocal/read.json and $OUT/GO"
until [ -s data/runs/build3-priocal/read.json ] && [ -f "$OUT/GO" ]; do sleep 120; done
log "launching the paired read"
NAME=b3e5 CKPT=data/training/m12-build3-e3/last.pt GAMES=300 WORKERS=24 SERVERS=2 PORT=50067 ARMS="on act" \
  FORGE_ARGS="-search -searchrate 1 -searchrolls 2 -searchsurf 2 -searchact 0.10 -searchtemp 0.025" \
  FORGE_ARGS_ACT="-searchactkinds mode" JAR="$OUT/forge-b3e5.jar" \
  nice -n 19 bash scripts/build3_surface_read.sh
log "paired read exited rc=$?"
