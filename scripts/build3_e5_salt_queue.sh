#!/usr/bin/env bash
# Evening 5 follow-ups behind the entity arm (ADR-0106 C1; ADR-0107 launcher):
#   1. the forkcheck on the salt tip (flag-off identity; the pin's proof)
#   2. the de-confounded end arm: the calibration chain with LEAVES=end under
#      -searchrollsalt (independent roll seeds; the same searched windows)
# Launched through anvil.runs (its dir = OUT); the forkcheck's java is
# detached by run_forkcheck.sh, so this script waits on its results file.
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=${OUT:-data/runs/build3-priocal-salt}; mkdir -p "$OUT"
FC=${FC:-$REPO/data/forkcheck/run-20260915-build3-e5salt}
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "waiting for b3e5-actent"
uv run python -m anvil.runs wait --name b3e5-actent --poll 60 || log "entity arm ended non-zero (continuing: the box is free)"
log "forkcheck start"
N_GAMES=500 SEED=20260703 bash scripts/forkcheck/run_forkcheck.sh "$FC" | tee -a "$OUT/queue.log"
log "salted end arm start"
OUT="$OUT" TAG=b3pcals SALT=20260915 LEAVES=end JAR="$OUT/forge-b3pcals.jar" bash scripts/build3_prio_calibration.sh || { log "salted arm FAILED"; exit 1; }
pid=$(cat "$FC/run.pid"); until [ ! -d /proc/$pid ] || [ "$(wc -l < $FC/results.jsonl 2>/dev/null || echo 0)" -ge 500 ]; do sleep 60; done
uv run python scripts/forkcheck/compare.py "$FC" | tee "$FC/compare.txt" | tee -a "$OUT/queue.log"
log "the four-arm read"
uv run python scripts/prio_calibration.py --arm next=$(cat data/runs/build3-priocal/next.done) --arm h2=$(cat data/runs/build3-priocal/h2.done) \
  --arm end=$(cat data/runs/build3-priocal/end.done) --arm endsalt=$(cat $OUT/end.done) --end endsalt --out "$OUT/read4.json" | tee "$OUT/read4.md" | tee -a "$OUT/queue.log"
log "queue done"
