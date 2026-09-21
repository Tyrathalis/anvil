#!/usr/bin/env bash
# 09-21 (ADR-0114 routed items): the void-census bundle's forkcheck, unattended —
# the tip cbe386d2c6 (vr unconditional, act_vr on the mainline's forced ask, copy:true on
# search-copy census rows) is recording-only, so the 500-game trace hashes must match the
# baseline (ADR-0025's empirical proof). Detached forkcheck -> wait -> compare.txt.
# Launch: uv run python -m anvil.runs launch --name build4-census-chain --dir data/runs/build4-census \
#           --watch 'data/forkcheck/run-20260921-build4-census' -- bash scripts/build4_census_chain.sh
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/build4-census; mkdir -p "$OUT"
JAR=$OUT/forge-census.jar; FC=$REPO/data/forkcheck/run-20260921-build4-census
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "chain start jar=$JAR ($(cat $OUT/forge-census.commit))"
if [[ ! -f "$FC/compare.txt" ]]; then
  N_GAMES=500 SEED=20260703 JAR="$JAR" bash scripts/forkcheck/run_forkcheck.sh "$FC" | tee -a "$OUT/queue.log"
  FC_PID=$(cat "$FC/run.pid")
  log "forkcheck detached pid=$FC_PID dir=$FC"
  until [ ! -d /proc/$FC_PID ] || { [ -f "$FC/results.jsonl" ] && [ "$(wc -l < "$FC/results.jsonl")" -ge 500 ]; }; do sleep 60; done
  uv run python scripts/forkcheck/compare.py "$FC" | tee "$FC/compare.txt" | tee -a "$OUT/queue.log"
fi
log "forkcheck done: $(grep -i "identical\|PASS\|FAIL" "$FC/compare.txt" | head -2 | tr '\n' ' ')"
echo OK > "$OUT/DONE"
