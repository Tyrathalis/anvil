#!/usr/bin/env bash
# The mask cache's obs-diff gate re-read (ADR-0102 consequences; ADR-0109's "re-read when
# convenient" — the engine binds since the 09-14 bench): two same-seed bridged arms on the
# SAME jar — cache OFF (-Danvil.scan.maskcache=off, the default) vs ON — then
# scripts/obs_diff.py window by window on the recorded masks and answers.
# ONE worker (the 09-14 rule: identity gates on served arms serve batches of one; at 8 workers
# the bf16 micro-batch composition flips near-tie picks), so the OFF/OFF control is identity
# (the memo gate: 32/32 games / 32,306 windows at one worker) and ANY mask-class first
# divergence = the ADR-0102 key gap persists = FAIL (the cache stays OFF).
# Usage: build4_maskcache_gate.sh [games=120]   env: JAR, CKPT, PORT, WORKERS
# Launched through anvil.runs (its dir = OUT).
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
PORT=${PORT:-50075}; CKPT=${CKPT:-$REPO/data/training/m12-build3-e3/last.pt}; GAMES=${1:-120}; WORKERS=${WORKERS:-1}
OUT=$REPO/data/runs/build4-maskcache-gate-w$WORKERS-g$GAMES; mkdir -p "$OUT"
JAR=${JAR:-$REPO/data/runs/merge-boundary/forge-flip-8137d0c41c.jar}
export PYTHONUNBUFFERED=1 DISPLAY=:0; export XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1)
cd "$REPO"; log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/gate.log"; }
notify() { python3 -c "from anvil.training.notify import notify; notify('$1', '$2', tag='maskcache')"; }
uv run python -m anvil.bridge.server --mode model --ckpt "$CKPT" --port $PORT --pass-delta 0 --stats-every 0 > "$OUT/server.log" 2>&1 &
SERVER=$!; for i in $(seq 1 300); do (echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null && break; sleep 2; done
log "server up $SERVER jar=$JAR"
for arm in off on; do
  t0=$(date +%s)
  ANVIL_EXTRA_JVM_OPTS="-Danvil.scan.maskcache=$arm" uv run python -m anvil.bridge.harness launch --pool --games "$GAMES" --games-per-pair 5 \
    --workers "$WORKERS" --bridge grpc:localhost:$PORT --census --obs --purpose "maskcache-gate-w$WORKERS-$arm" --jar "$JAR" \
    --seed-base 20260916 --bridge-seats 0 --reask --no-yield-gpu > "$OUT/arm-$arm.log" 2>&1
  log "arm $arm rc=$? wall=$(( $(date +%s) - t0 ))s"
done
kill -TERM $SERVER 2>/dev/null; sleep 3; kill -KILL $SERVER 2>/dev/null
A=$(ls -d $REPO/data/runs/maskcache-gate-w$WORKERS-off-* | tail -1); B=$(ls -d $REPO/data/runs/maskcache-gate-w$WORKERS-on-* | tail -1)
for d in $A $B; do uv run python -m anvil.store ingest "$d" > "$OUT/ingest-$(basename $d).log" 2>&1; done
SA=$REPO/data/trajectories/$(basename $A); SB=$REPO/data/trajectories/$(basename $B)
uv run python scripts/obs_diff.py "$SA" "$SB" > "$OUT/obs-diff.txt" 2>&1; rc=$?
log "obs-diff rc=$rc -> $OUT/obs-diff.txt: $(tail -1 $OUT/obs-diff.txt)"
echo "rc=$rc" > "$OUT/DONE"; notify "anvil mask-cache gate DONE rc=$rc" "$(tail -1 $OUT/obs-diff.txt)"
