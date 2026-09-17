#!/usr/bin/env bash
# Build 4 (09-17): the forkcheck of the veto-fallback tip (flag off = the re-ask path unchanged).
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/build4-targets-vetofb; mkdir -p "$OUT"
JAR=$REPO/data/runs/build4-targets/forge-vetofb.jar; FC=$REPO/data/forkcheck/run-20260917-build4-vetofb
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "forkcheck start jar=$JAR ($(cat data/runs/build4-targets/forge-vetofb.commit))"
N_GAMES=500 SEED=20260703 JAR="$JAR" bash scripts/forkcheck/run_forkcheck.sh "$FC" | tee -a "$OUT/queue.log"
pid=$(cat "$FC/run.pid"); until [ ! -d /proc/$pid ] || { [ -f "$FC/results.jsonl" ] && [ "$(wc -l < "$FC/results.jsonl")" -ge 500 ]; }; do sleep 60; done
uv run python scripts/forkcheck/compare.py "$FC" | tee "$FC/compare.txt" | tee -a "$OUT/queue.log"
echo OK > "$OUT/DONE"
