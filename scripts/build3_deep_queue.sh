#!/usr/bin/env bash
# The partial-expansion slot (ADR-0106 C3, 09-15): the proof + the price, in
# order on one jar snapshot (JAR):
#   1. the forkcheck on the deep tip (flag-off identity; the pin's proof) —
#      run_forkcheck.sh detaches its java, so this script waits on results.jsonl
#   2. the bench cell pair at 24 x 2, 64 games each, on a quiet box:
#      recipe = the ADR-0106 recipe arm (rate 1, rolls 2, surf 2, acting on
#      entity_one/entity_set/mode at bar 0.10); deep = recipe + -searchdeep 3
#      (h2, rolls 4, band lo 0.02, floor 0.1). The read = the deep share of
#      forward calls per game from the cells' labels (the per-lever number)
#      and the g/h ratio (one cell per arm: a draw, not a read — the 09-14
#      rule; the ratio is what the equal-box-time split needs).
# Launched through anvil.runs (its dir = OUT).
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=${OUT:-$REPO/data/runs/build3-deep}; case "$OUT" in /*) ;; *) OUT="$REPO/$OUT" ;; esac; mkdir -p "$OUT"
JAR=${JAR:-$OUT/forge-deep.jar}
FC=${FC:-$REPO/data/forkcheck/run-20260915-build3-deep}
RECIPE="-search -searchrate 1 -searchrolls 2 -searchsurf 2 -searchact 0.10 -searchtemp 0.025 -searchactkinds entity_one,entity_set,mode"
DEEPARGS=${DEEPARGS:-"-searchdeep 3 -searchdeepleaf h2 -searchdeeprolls 4 -searchdeeplo 0.02 -searchdeepfloor 0.1 -searchclock 3600"}
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
if [[ -z "${SKIP_FC:-}" ]]; then
  log "forkcheck start jar=$JAR"
  N_GAMES=500 SEED=20260703 JAR="$JAR" bash scripts/forkcheck/run_forkcheck.sh "$FC" | tee -a "$OUT/queue.log"
  pid=$(cat "$FC/run.pid"); until [ ! -d /proc/$pid ] || { [ -f "$FC/results.jsonl" ] && [ "$(wc -l < "$FC/results.jsonl")" -ge 500 ]; }; do sleep 60; done
  uv run python scripts/forkcheck/compare.py "$FC" | tee "$FC/compare.txt" | tee -a "$OUT/queue.log"
  log "forkcheck compared (read compare.txt; the bench does not wait on the verdict)"
fi
log "bench cell: recipe"
uv run python scripts/fleet_bench.py --jar "$JAR" --cells 24:2 --games 64 --port 50090 --name deep-bench-recipe --forge-args="$RECIPE" >> "$OUT/bench-recipe.log" 2>&1 || { log "recipe cell FAILED"; exit 1; }
log "bench cell: deep"
uv run python scripts/fleet_bench.py --jar "$JAR" --cells 24:2 --games 64 --port 50090 --name deep-bench-deep --forge-args="$RECIPE $DEEPARGS" >> "$OUT/bench-deep.log" 2>&1 || { log "deep cell FAILED"; exit 1; }
log "the cost read"
uv run python scripts/deep_bench_read.py data/runs/deep-bench-recipe data/runs/deep-bench-deep | tee "$OUT/read.md" | tee -a "$OUT/queue.log"
log "queue done"
