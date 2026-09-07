#!/usr/bin/env bash
# M12 Build 2 acting-rule smoke (m12-plan Build 2): the search directive as the
# BEHAVIOR POLICY on the seat-0 bridged mainline vs the heuristic — every
# quiescent main-phase window searched (-searchrate 1), the acting rule at
# -searchact <bar> / -searchtemp <T>, the day-zero ckpt serving the mainline
# policy, the copies and the leaf values. Reads: scripts/build2_read.py smoke.
# Usage: build2_act_smoke.sh [games=8] [bar=0.05] [temp=0.025] [rate=1.0]
#   env: OUT, CKPT, JAR, PORT, SEED, SEATS (default "0")
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
FORGE=/home/tyrathalis/Everything/Projects/forge
JAR=${JAR:-$(ls -t $FORGE/forge-gui-desktop/target/*jar-with-dependencies.jar | head -1)}
OUT=${OUT:-$REPO/data/runs/build2-act-smoke}
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT" ;; esac
mkdir -p "$OUT"
PORT=${PORT:-50073}
CKPT=${CKPT:-$REPO/data/training/m12-build1-stopstate/last.pt}
GAMES=${1:-8}; BAR=${2:-0.05}; TEMP=${3:-0.025}; RATE=${4:-1.0}
SEED=${SEED:-20260906}; SEATS=${SEATS:-0}
export PYTHONUNBUFFERED=1 DISPLAY=:0
export XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1)
cd "$REPO"
log() { echo "$(date -Iseconds) $*"; }
log "jar $JAR ckpt $CKPT"
uv run python -m anvil.bridge.server --mode model --ckpt "$CKPT" --port $PORT --pass-delta 0 \
  > "$OUT/server.log" 2>&1 &
SERVER=$!
for i in $(seq 1 300); do (echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null && break; sleep 2; done
(echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null || { log "server never opened port"; kill $SERVER; exit 1; }
log "server up pid=$SERVER"
rm -f "$OUT/search.jsonl" "$OUT/games.jsonl" "$OUT/census.jsonl" "$OUT/obs.zst" "$OUT/obs.idx.jsonl"
t0=$(date +%s)
( cd "$FORGE/forge-gui" && nice -n 19 java -Xmx3g -jar "$JAR" anvil \
    -d "dc-863946.dck" "dc-864920.dck" -f Commander -n "$GAMES" -s "$SEED" \
    -b grpc:localhost:$PORT -reask -bridgeseats "$SEATS" -pool cf2ca6ba \
    -forkcommit "$(git -C $FORGE rev-parse HEAD)" \
    -search -searchrate "$RATE" -searchact "$BAR" -searchtemp "$TEMP" -searchseats "$SEATS" \
    -labels "$OUT/search.jsonl" -results "$OUT/games.jsonl" -census "$OUT/census.jsonl" -obs "$OUT/obs.zst" \
    > "$OUT/anvil.log" 2>&1 )
rc=$?; t1=$(date +%s)
log "anvil rc=$rc wall=$((t1-t0))s"
kill -TERM $SERVER 2>/dev/null; sleep 3; kill -KILL $SERVER 2>/dev/null
echo "{\"games\":$GAMES,\"bar\":$BAR,\"temp\":$TEMP,\"rate\":$RATE,\"rc\":$rc,\"wall_s\":$((t1-t0))}" > "$OUT/DONE"
