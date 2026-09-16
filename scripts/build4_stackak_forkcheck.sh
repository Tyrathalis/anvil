#!/usr/bin/env bash
# Build 4: the forkcheck of the stack-key tip (ObsSnapshot's ak on stack entries; recording-only),
# queued behind the gate tip's (data/runs/build4-targets-gate/DONE). Launched through anvil.runs.
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=${OUT:-$REPO/data/runs/build4-targets-stackak}; mkdir -p "$OUT"
JAR=${JAR:-$REPO/data/runs/build4-targets/forge-stackak.jar}
FC=${FC:-$REPO/data/forkcheck/run-20260916-build4-stackak}
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "waiting for data/runs/build4-targets-gate/DONE and $JAR"
until [ -f data/runs/build4-targets-gate/DONE ] && [ -f "$JAR" ]; do sleep 60; touch "$OUT/.waiting"; done
log "forkcheck start jar=$JAR ($(cat data/runs/build4-targets/forge-stackak.commit))"
N_GAMES=500 SEED=20260703 JAR="$JAR" bash scripts/forkcheck/run_forkcheck.sh "$FC" | tee -a "$OUT/queue.log"
pid=$(cat "$FC/run.pid"); until [ ! -d /proc/$pid ] || { [ -f "$FC/results.jsonl" ] && [ "$(wc -l < "$FC/results.jsonl")" -ge 500 ]; }; do sleep 60; done
uv run python scripts/forkcheck/compare.py "$FC" | tee "$FC/compare.txt" | tee -a "$OUT/queue.log"
echo OK > "$OUT/DONE"
