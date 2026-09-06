#!/usr/bin/env bash
# M12 Build 0 smoke chain (ADR-0102 consequences, step d): on the boundary jar,
#   A: bridged 600 games, iter-019 argmax vs heuristic (seat 0), filter ON, cache OFF
#   B: same seeds, mask cache ON            -> obs-diff gate + games/hour delta
#   C: 200 games, payshadow ON              -> the enumerator-rescue class
#   then the 500-game heuristic forkcheck vs the 08-21 seed set (the boundary proof).
# Detached by the launcher (setsid nohup); writes DONE in $OUT when the chain ends.
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
OUT=$REPO/data/runs/build0-smoke
PORT=50071
CKPT=$REPO/data/training/d6-run11/iter-019/train/last.pt
SEEDBASE=20260906
export PYTHONUNBUFFERED=1
export DISPLAY=:0
export XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1)
cd "$REPO"
log() { echo "$(date -Iseconds) $*"; }

log "server start"
uv run python -m anvil.bridge.server --mode model --ckpt "$CKPT" --port $PORT --pass-delta 0 \
  > "$OUT/server.log" 2>&1 &
SERVER=$!
for i in $(seq 1 300); do (echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null && break; sleep 2; done
(echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null || { log "server never opened port $PORT"; kill $SERVER; echo FAIL > "$OUT/DONE"; exit 1; }
log "server up pid=$SERVER"

run_arm() { # name games extra_jvm
  local name=$1 games=$2 jvm=$3
  log "arm $name start (games=$games jvm='$jvm')"
  local t0=$(date +%s)
  ANVIL_EXTRA_JVM_OPTS="$jvm" uv run python -m anvil.bridge.harness launch --pool --games "$games" \
    --games-per-pair 5 --workers 16 --chunk 200 --bridge grpc:localhost:$PORT --census --obs \
    --purpose "build0-smoke$name" --seed-base $SEEDBASE --bridge-seats 0 --reask \
    > "$OUT/arm-$name.log" 2>&1
  local rc=$? t1=$(date +%s)
  echo "{\"arm\":\"$name\",\"games\":$games,\"jvm\":\"$jvm\",\"rc\":$rc,\"t0\":$t0,\"t1\":$t1,\"wall_s\":$((t1-t0))}" >> "$OUT/arms.jsonl"
  log "arm $name done rc=$rc wall=$((t1-t0))s"
}
run_arm A 600 ""
run_arm B 600 "-Danvil.scan.maskcache=on"
run_arm C 200 "-Danvil.scan.payshadow=on"

log "server stop"
kill -TERM $SERVER 2>/dev/null; sleep 5; kill -KILL $SERVER 2>/dev/null

log "forkcheck start"
N_GAMES=500 SEED=20260703 bash scripts/forkcheck/run_forkcheck.sh "$REPO/data/forkcheck/run-20260906-build0-boundary" > "$OUT/forkcheck-launch.log" 2>&1
FPID=$(cat "$REPO/data/forkcheck/run-20260906-build0-boundary/run.pid")
while [ -e /proc/$FPID ]; do sleep 30; done
log "forkcheck done"
echo OK > "$OUT/DONE"
