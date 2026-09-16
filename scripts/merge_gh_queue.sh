#!/usr/bin/env bash
# ADR-0110: the flip tip (views default ON + the fork's console modes headless)
# proven against the merge baseline, then the three-cell g/h read on its jar
# (24 x 2, the recipe arm, 64 games per cell, three seed bases — the 09-14 rule:
# g/h reads need >= 3 cells per arm). Launched through anvil.runs (dir = OUT).
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=${OUT:-$REPO/data/runs/merge-boundary}; mkdir -p "$OUT"
JAR=${JAR:?the flip tip jar snapshot}
FORGE_DIR=${FORGE_DIR:-/home/tyrathalis/Everything/Projects/forge-merge}
FC=${FC:-$REPO/data/forkcheck/run-20260916-merge-flip}
CKPT=${CKPT:-data/training/m12-build3-e3/last.pt}
RECIPE="-search -searchrate 1 -searchrolls 2 -searchsurf 2 -searchact 0.10 -searchtemp 0.025 -searchactkinds entity_one,entity_set,mode"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/gh.log"; }
if [[ -z "${SKIP_FC:-}" ]]; then
  log "flip-tip forkcheck jar=$JAR"
  N_GAMES=500 SEED=20260703 JAR="$JAR" FORGE_DIR="$FORGE_DIR" bash scripts/forkcheck/run_forkcheck.sh "$FC" | tee -a "$OUT/gh.log"
  pid=$(cat "$FC/run.pid"); until [ ! -d /proc/$pid ] || [ "$(wc -l < "$FC/results.jsonl" 2>/dev/null || echo 0)" -ge 500 ]; do sleep 60; done
  uv run python scripts/forkcheck/compare.py "$FC" | tee "$FC/compare.txt" | tee -a "$OUT/gh.log"
  log "flip-tip forkcheck compared (read $FC/compare.txt)"
fi
for k in 1 2 3; do
  log "g/h cell $k (24:2, recipe)"
  uv run python scripts/fleet_bench.py --ckpt "$CKPT" --jar "$JAR" --cells 24:2 --games 64 --port 50090 \
      --seed-base $((20260916 + k)) --name "merge-gh-$k" --forge-args="$RECIPE" >> "$OUT/gh-$k.log" 2>&1 || { log "cell $k FAILED"; exit 1; }
done
log "g/h cells done: read data/runs/merge-gh-{1,2,3}/bench.md (peak g/h per cell; the median of three = the recipe's rate on the merged jar)"
