#!/usr/bin/env bash
# M12 Build 3 surface smoke (ADR-0103): the one-ply search directive with the
# surface-expansion round (-searchsurf B) on the surfaces jar — bridged
# self-play games on iter-019, a sampled fraction of the active seat's
# quiescent main-phase windows searched, the first traced surface callback on
# the top-B candidates' paths expanded (one copy per enumerated answer). Reads:
# scripts/surface_smoke_read.py.
# Usage: build3_surface_smoke.sh [games=12] [rate=0.2] [surf=2] [cap=8]
#   env: OUT, PORT, CKPT (a fitted surface ckpt serves the surface tags — ADR-0105), JAR
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
FORGE=/home/tyrathalis/Everything/Projects/forge
JAR=$(ls -t $FORGE/forge-gui-desktop/target/*jar-with-dependencies.jar | head -1)
OUT=${OUT:-$REPO/data/runs/build3-surface-smoke}
PORT=${PORT:-50073}
CKPT=${CKPT:-$REPO/data/training/d6-run11/iter-019/train/last.pt}
JAR=${JAR:-$JAR}
GAMES=${1:-12}; RATE=${2:-0.2}; SURF=${3:-2}; CAP=${4:-8}
export PYTHONUNBUFFERED=1 DISPLAY=:0
export XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1)
mkdir -p "$OUT"
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
    -d "dc-863946.dck" "dc-864920.dck" -f Commander -n "$GAMES" -s 20260907 \
    -b grpc:localhost:$PORT -reask -pool cf2ca6ba -forkcommit "$(git -C $FORGE rev-parse HEAD)" \
    -search -searchrate "$RATE" -searchrolls 1 -searchsurf "$SURF" -searchsurfcap "$CAP" \
    -labels "$OUT/search.jsonl" \
    -results "$OUT/games.jsonl" -census "$OUT/census.jsonl" -obs "$OUT/obs.zst" \
    > "$OUT/anvil.log" 2>&1 )
rc=$?; t1=$(date +%s)
log "anvil rc=$rc wall=$((t1-t0))s"
kill -TERM $SERVER 2>/dev/null; sleep 3; kill -KILL $SERVER 2>/dev/null
echo "{\"games\":$GAMES,\"rate\":$RATE,\"surf\":$SURF,\"cap\":$CAP,\"rc\":$rc,\"wall_s\":$((t1-t0))}" > "$OUT/DONE"
