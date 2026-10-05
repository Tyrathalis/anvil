#!/usr/bin/env bash
# THE UNFIT-FLAG FIX'S FORKCHECK (ADR-0122, 10-04 night): fork 5bd040351f (every targeting node below a Charm node
# is a mode node — Cryptic Command's stale bound mode no longer reads as unfit) is recording-only; the standing
# 500-seed trace-hash read against the 09-16 merge baseline is its ADR-0025 proof. PASS (identical but for the
# standing seed 20260969) moves the pin to 5bd040351f; the jar data/runs/tgtmask/forge-tgtmask3.jar then serves.
# Launch: uv run python -m anvil.runs launch --name tgtmask-tzfix --dir data/runs/tgtmask-tzfix \
#   --launched-by '<ListAgents name> [<ref>]' --watch 'data/forkcheck/run-20261004-tgtmask3' --stall-min 60 \
#   -- bash scripts/tgtmask_tzfix_forkcheck.sh
set -u
REPO=${REPO:-$(cd "$(dirname "$0")/.." && pwd)}; cd "$REPO"
OUT=$REPO/data/runs/tgtmask-tzfix; mkdir -p "$OUT"
JAR=${JAR:-$REPO/data/runs/tgtmask/forge-tgtmask3.jar}
FC=${FC:-$REPO/data/forkcheck/run-20261004-tgtmask3}
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
[[ -f "$JAR" ]] || { log "no jar at $JAR"; exit 1; }
log "forkcheck start jar=$JAR ($(cat "$REPO/data/runs/tgtmask/forge-tgtmask3.commit" 2>/dev/null))"
N_GAMES=500 SEED=20260703 JAR="$JAR" bash scripts/forkcheck/run_forkcheck.sh "$FC" | tee -a "$OUT/queue.log"
pid=$(cat "$FC/run.pid")
until [ ! -d /proc/$pid ] || { [ -f "$FC/results.jsonl" ] && [ "$(wc -l < "$FC/results.jsonl")" -ge 500 ]; }; do
  sleep 60; touch "$OUT/.waiting"
done
uv run python scripts/forkcheck/compare.py "$FC" | tee "$FC/compare.txt" | tee -a "$OUT/queue.log"
log "done"; echo OK > "$OUT/DONE"
