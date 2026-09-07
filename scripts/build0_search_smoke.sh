#!/usr/bin/env bash
# M12 Build 0 search smoke (ADR-0102 consequences, step e): the one-ply search
# directive on the search jar, a few bridged self-play games (both seats
# bridged, iter-019 argmax mainline; search copies served greedy), every
# active-seat quiescent main-phase window searched (-searchrate 1), one
# determinization per option. Reads: scripts/search_smoke_read.py.
# Usage: build0_search_smoke.sh [games=12] [rate=1.0] [rolls=1]
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
FORGE=/home/tyrathalis/Everything/Projects/forge
JAR=$(ls -t $FORGE/forge-gui-desktop/target/*jar-with-dependencies.jar | head -1)
OUT=${OUT:-$REPO/data/runs/build0-search-smoke}
mkdir -p "$OUT"
PORT=50072
CKPT=${CKPT:-$REPO/data/training/d6-run11/iter-019/train/last.pt}
GAMES=${1:-12}; RATE=${2:-1.0}; ROLLS=${3:-1}
export PYTHONUNBUFFERED=1 DISPLAY=:0
export XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1)
cd "$REPO"
log() { echo "$(date -Iseconds) $*"; }
log "jar $JAR"
uv run python -m anvil.bridge.server --mode model --ckpt "$CKPT" --port $PORT --pass-delta 0 \
  > "$OUT/server.log" 2>&1 &
SERVER=$!
for i in $(seq 1 300); do (echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null && break; sleep 2; done
(echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null || { log "server never opened port"; kill $SERVER; exit 1; }
log "server up pid=$SERVER"
rm -f "$OUT/search.jsonl" "$OUT/games.jsonl" "$OUT/census.jsonl" "$OUT/obs.zst" "$OUT/obs.idx.jsonl"
t0=$(date +%s)
( cd "$FORGE/forge-gui" && nice -n 19 java -Xmx3g -jar "$JAR" anvil \
    -d "dc-863946.dck" "dc-864920.dck" -f Commander -n "$GAMES" -s 20260906 \
    -b grpc:localhost:$PORT -reask -pool cf2ca6ba -forkcommit "$(git -C $FORGE rev-parse HEAD)" \
    -search -searchrate "$RATE" -searchrolls "$ROLLS" -labels "$OUT/search.jsonl" \
    -results "$OUT/games.jsonl" -census "$OUT/census.jsonl" -obs "$OUT/obs.zst" \
    > "$OUT/anvil.log" 2>&1 )
rc=$?; t1=$(date +%s)
log "anvil rc=$rc wall=$((t1-t0))s"
kill -TERM $SERVER 2>/dev/null; sleep 3; kill -KILL $SERVER 2>/dev/null
echo "{\"games\":$GAMES,\"rate\":$RATE,\"rolls\":$ROLLS,\"rc\":$rc,\"wall_s\":$((t1-t0))}" > "$OUT/DONE"
