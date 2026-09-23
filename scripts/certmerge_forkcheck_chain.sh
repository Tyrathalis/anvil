#!/usr/bin/env bash
# 09-23 (ADR-0117, the certifier merge): the -replay front's forkcheck, unattended, inside a
# shakedown pause window — the tip touches the game path only behind -replay (the pick hook is a
# read-only observer on the mainline's natural pick; SurfaceDirective's exec record is written on
# search copies only), so the 500-game trace hashes must match the baseline (ADR-0025's empirical
# proof). Detached forkcheck -> wait -> compare.txt.
# Launch (the shakedown PAUSED at an iteration boundary first — `anvil.runs pause --name shakedown`,
# then `anvil.runs relaunch --name shakedown` when DONE lands):
#   uv run python -m anvil.runs launch --name certmerge-forkcheck --dir data/runs/certmerge \
#     --watch 'data/forkcheck/run-20260923-certmerge' -- bash scripts/certmerge_forkcheck_chain.sh
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/certmerge; mkdir -p "$OUT"
JAR=$OUT/forge-certmerge.jar; FC=$REPO/data/forkcheck/run-20260923-certmerge
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "chain start jar=$JAR ($(cat $OUT/forge-certmerge.commit))"
if [[ ! -f "$FC/compare.txt" ]]; then
  N_GAMES=500 SEED=20260703 JAR="$JAR" bash scripts/forkcheck/run_forkcheck.sh "$FC" | tee -a "$OUT/queue.log"
  FC_PID=$(cat "$FC/run.pid")
  log "forkcheck detached pid=$FC_PID dir=$FC"
  until [ ! -d /proc/$FC_PID ] || { [ -f "$FC/results.jsonl" ] && [ "$(wc -l < "$FC/results.jsonl")" -ge 500 ]; }; do sleep 60; done
  uv run python scripts/forkcheck/compare.py "$FC" | tee "$FC/compare.txt" | tee -a "$OUT/queue.log"
fi
log "forkcheck done: $(grep -i "identical\|PASS\|FAIL" "$FC/compare.txt" | head -2 | tr '\n' ' ')"
echo OK > "$OUT/DONE"
