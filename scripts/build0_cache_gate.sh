#!/usr/bin/env bash
# The mask-cache obs-diff gate on the RNG-neutral scan (ADR-0102 consequences):
# two same-seed bridged arms (cache OFF / ON), N games, then scripts/obs_diff.py.
# Usage: build0_cache_gate.sh [games=120]
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; OUT=$REPO/data/runs/build0-cache-gate; mkdir -p "$OUT"
PORT=50073; CKPT=$REPO/data/training/d6-run11/iter-019/train/last.pt; GAMES=${1:-120}
export PYTHONUNBUFFERED=1 DISPLAY=:0; export XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1)
cd "$REPO"; log() { echo "$(date -Iseconds) $*"; }
uv run python -m anvil.bridge.server --mode model --ckpt "$CKPT" --port $PORT --pass-delta 0 > "$OUT/server.log" 2>&1 &
SERVER=$!; for i in $(seq 1 300); do (echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null && break; sleep 2; done
log "server up $SERVER"
for arm in off on; do
  jvm=""; [ $arm = on ] && jvm="-Danvil.scan.maskcache=on"
  t0=$(date +%s)
  ANVIL_EXTRA_JVM_OPTS="$jvm" uv run python -m anvil.bridge.harness launch --pool --games "$GAMES" --games-per-pair 5 \
    --workers 8 --chunk 15 --bridge grpc:localhost:$PORT --census --obs --purpose "build0-cache-$arm" \
    --seed-base 20260907 --bridge-seats 0 --reask > "$OUT/arm-$arm.log" 2>&1
  log "arm $arm rc=$? wall=$(( $(date +%s) - t0 ))s"
done
kill -TERM $SERVER 2>/dev/null; sleep 3; kill -KILL $SERVER 2>/dev/null
A=$(ls -d $REPO/data/runs/build0-cache-off-* | tail -1); B=$(ls -d $REPO/data/runs/build0-cache-on-* | tail -1)
for d in $A $B; do uv run python -m anvil.store ingest "$d" > /dev/null 2>&1; done
SA=$REPO/data/trajectories/$(basename $A); SB=$REPO/data/trajectories/$(basename $B)
uv run python scripts/obs_diff.py "$SA" "$SB" > "$OUT/obs-diff.txt" 2>&1
log "obs-diff rc=$? -> $OUT/obs-diff.txt"; echo OK > "$OUT/DONE"
