#!/usr/bin/env bash
# The mana-source memo's identity gate (2026-09-14; the 08-11 obs-diff protocol):
# two same-seed bridged arms on the SAME jar — memo OFF (-Danvil.scan.sourcememo=off,
# the per-candidate rebuild) vs ON — then scripts/obs_diff.py window by window on the
# recorded masks and answers. Exact by construction => 0 divergent games.
# Usage: build3_memo_gate.sh [games=120]   env: JAR, CKPT, PORT, WORKERS
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; OUT=$REPO/data/runs/build3-memo-gate; mkdir -p "$OUT"
PORT=${PORT:-50074}; CKPT=${CKPT:-$REPO/data/training/m12-build3-e3/last.pt}; GAMES=${1:-120}; WORKERS=${WORKERS:-8}
JAR=${JAR:-$REPO/data/runs/build3-memo/forge-memo.jar}
export PYTHONUNBUFFERED=1 DISPLAY=:0; export XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1)
cd "$REPO"; log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/gate.log"; }
notify() { python3 -c "from anvil.training.notify import notify; notify('$1', '$2', tag='memo')"; }
python3 scripts/anvil_watchd.py register --name memo-gate --pid $$ --dir "$REPO/data/runs" --stall-min 45
uv run python -m anvil.bridge.server --mode model --ckpt "$CKPT" --port $PORT --pass-delta 0 --stats-every 0 > "$OUT/server.log" 2>&1 &
SERVER=$!; for i in $(seq 1 300); do (echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null && break; sleep 2; done
log "server up $SERVER jar=$JAR ($(cat ${JAR%.jar}.commit 2>/dev/null))"
for arm in off on; do
  t0=$(date +%s)
  ANVIL_EXTRA_JVM_OPTS="-Danvil.scan.sourcememo=$arm" nice -n 19 uv run python -m anvil.bridge.harness launch --pool --games "$GAMES" --games-per-pair 5 \
    --workers "$WORKERS" --chunk 15 --bridge grpc:localhost:$PORT --census --obs --purpose "memo-gate-$arm" --jar "$JAR" \
    --seed-base 20260914 --bridge-seats 0 --reask --no-yield-gpu > "$OUT/arm-$arm.log" 2>&1
  log "arm $arm rc=$? wall=$(( $(date +%s) - t0 ))s"
done
kill -TERM $SERVER 2>/dev/null; sleep 3; kill -KILL $SERVER 2>/dev/null
A=$(ls -d $REPO/data/runs/memo-gate-off-* | tail -1); B=$(ls -d $REPO/data/runs/memo-gate-on-* | tail -1)
for d in $A $B; do uv run python -m anvil.store ingest "$d" > "$OUT/ingest-$(basename $d).log" 2>&1; done
SA=$REPO/data/trajectories/$(basename $A); SB=$REPO/data/trajectories/$(basename $B)
uv run python scripts/obs_diff.py "$SA" "$SB" > "$OUT/obs-diff.txt" 2>&1; rc=$?
log "obs-diff rc=$rc -> $OUT/obs-diff.txt: $(tail -1 $OUT/obs-diff.txt)"
python3 scripts/anvil_watchd.py unregister --name memo-gate
echo "rc=$rc" > "$OUT/DONE"; notify "anvil memo gate DONE rc=$rc" "$(tail -1 $OUT/obs-diff.txt)"
