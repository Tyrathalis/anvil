#!/usr/bin/env bash
# ADR-0110 (the 2026-09-16 upstream merge): the boundary's forkcheck pair on the
# merged jar snapshot (JAR), in order:
#   1. the NEW BASELINE — flag-off, the standing seed set 20260703+500; compared
#      against the 08-21 baseline for the record only (a boundary: hashes move)
#   2. the views-flag PROOF — -Danvil.nogui=on on the same jar, compared against
#      the new baseline (ADR-0025: identical trace hashes, or the flag stays off)
# Each forkcheck detaches its java (run_forkcheck.sh); this script waits on
# results.jsonl. Launched through anvil.runs (its dir = OUT).
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=${OUT:-$REPO/data/runs/merge-boundary}; mkdir -p "$OUT"
JAR=${JAR:-$OUT/forge-merge-1db054ade4.jar}
FORGE_DIR=${FORGE_DIR:-/home/tyrathalis/Everything/Projects/forge-merge}
BASE=${BASE:-$REPO/data/forkcheck/run-20260916-merge-baseline}
PROOF=${PROOF:-$REPO/data/forkcheck/run-20260916-merge-nogui}
OLD=$REPO/data/forkcheck/run-20260821-m9boundary
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
# the file test first: `wc -l < missing` errors past the 2>/dev/null before the first row lands (peer fix c8ad6de)
wait_fc() { local pid; pid=$(cat "$1/run.pid"); until [ ! -d /proc/$pid ] || { [ -f "$1/results.jsonl" ] && [ "$(wc -l < "$1/results.jsonl")" -ge 500 ]; }; do sleep 60; done; }

log "1/2 baseline forkcheck (flag off) jar=$JAR"
N_GAMES=500 SEED=20260703 JAR="$JAR" FORGE_DIR="$FORGE_DIR" bash scripts/forkcheck/run_forkcheck.sh "$BASE" | tee -a "$OUT/queue.log"
wait_fc "$BASE"
uv run python scripts/forkcheck/compare.py "$BASE" --baseline "$OLD" | tee "$BASE/compare-vs-0821.txt" | tee -a "$OUT/queue.log"
log "baseline landed: $(wc -l < "$BASE/results.jsonl") rows (the compare above is the boundary's drift vs 08-21, for the record)"

log "2/2 views-flag proof forkcheck (-Danvil.nogui=on) jar=$JAR"
N_GAMES=500 SEED=20260703 JAR="$JAR" FORGE_DIR="$FORGE_DIR" JVM_ARGS="-Danvil.nogui=on" bash scripts/forkcheck/run_forkcheck.sh "$PROOF" | tee -a "$OUT/queue.log"
wait_fc "$PROOF"
uv run python scripts/forkcheck/compare.py "$PROOF" --baseline "$BASE" | tee "$PROOF/compare.txt" | tee -a "$OUT/queue.log"
log "proof compared (read $PROOF/compare.txt: identical => the flag's default may flip)"
log "queue done"
