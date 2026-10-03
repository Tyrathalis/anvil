#!/usr/bin/env bash
# 10-03 (ADR-0121, the shuffle mark): the ADR-0025 proof for fork commit 8d82dfa546 — every
# Player.shuffle on a STORE session's game lands as a mark record; search / fidelity copies and
# the game path are untouched, so the 500-game main-trace hashes must match the 09-16 baseline.
# Held since 09-27 for the quiet box after the settings pass (ADR-0121 §2); the pin and the
# fork-lineage row move on PASS. Detached forkcheck -> wait -> compare.txt (ADR-0117's chain shape).
# Launch (box quiet):
#   uv run python -m anvil.runs launch --name shufflemark-forkcheck --dir data/runs/shufflemark \
#     --watch data/forkcheck/run-20261003-shufflemark -- bash scripts/shufflemark_forkcheck_chain.sh
set -u
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"; cd "$REPO"
DATA=/home/tyrathalis/Everything/Projects/Anvil/data
OUT=$DATA/runs/shufflemark; mkdir -p "$OUT"
JAR=$OUT/forge-shufflemark.jar; FC=$DATA/forkcheck/run-20261003-shufflemark
BASE=$DATA/forkcheck/run-20260916-merge-baseline
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "chain start jar=$JAR ($(head -c 60 $OUT/JAR.txt))"
if [[ ! -f "$FC/compare.txt" ]]; then
  N_GAMES=500 SEED=20260703 JAR="$JAR" bash scripts/forkcheck/run_forkcheck.sh "$FC" | tee -a "$OUT/queue.log"
  FC_PID=$(cat "$FC/run.pid")
  log "forkcheck detached pid=$FC_PID dir=$FC"
  until [ ! -d /proc/$FC_PID ] || { [ -f "$FC/results.jsonl" ] && [ "$(wc -l < "$FC/results.jsonl")" -ge 500 ]; }; do sleep 60; done
  uv run python scripts/forkcheck/compare.py "$FC" --baseline "$BASE" | tee "$FC/compare.txt" | tee -a "$OUT/queue.log"
fi
log "forkcheck done: $(grep -i "identical\|PASS\|FAIL" "$FC/compare.txt" | head -2 | tr '\n' ' ')"
echo OK > "$OUT/DONE"
