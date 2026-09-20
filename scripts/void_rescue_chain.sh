#!/usr/bin/env bash
# ADR-0114 (09-19): the void-rescue instrument's chain, unattended —
#   1. the forkcheck of the rescue tip (flag off = byte-identical: no rescue copy, no record),
#      detached, in parallel with the arm (each on its own dir);
#   2. THE INSTRUMENT ARM: the served build under the recipe (rate 1, rolls 2, surfaces +
#      surface acting at 0.10, NO allocation head — every candidate window searched, the most
#      void samples per game) + -searchvoidrescue, GAMES games per seat vs the heuristic on the
#      final_read pairs, 24 x 2. The rescued values never enter the acting rule: the arm's
#      strength is the recipe's (a sanity number), the read is in the rows;
#   3. the read (scripts/void_rescue_read.py): the void class by reason / group, the rescue
#      rate and the refusals, the rescued leaf value vs the best valued candidate and the
#      natural line on the same roll seed, the windows where a rescue clears the acting bar,
#      the price, the plan census -> void-rescue-read.{txt,json} in the read dir.
# Launch: uv run python -m anvil.runs launch --name build4-voidrescue-chain --dir data/runs/build4-voidrescue \
#           --watch 'data/runs/b4vr-*' -- bash scripts/void_rescue_chain.sh
#   env: CKPT (the served build), GAMES (150 / seat), WORKERS (24), SKIP_FORKCHECK (unset), BAR (0.10)
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/build4-voidrescue; mkdir -p "$OUT"
JAR=$OUT/forge-vr.jar; FC=$REPO/data/forkcheck/run-20260919-build4-voidrescue
CKPT=${CKPT:-data/training/m12-build4-e1a/last.pt}
GAMES=${GAMES:-150}; WORKERS=${WORKERS:-24}; BAR=${BAR:-0.10}
RECIPE="-search -searchrate 1 -searchrolls 2 -searchsurf 2 -searchsurfcap 8 -searchact 0.10 -searchtemp 0.025 -searchactkinds entity_one,entity_set,mode"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "chain start jar=$JAR ($(cat $OUT/forge-vr.commit)) ckpt=$CKPT games=$GAMES/seat workers=$WORKERS bar=$BAR"
FC_PID=
if [[ -z "${SKIP_FORKCHECK:-}" && ! -f "$FC/compare.txt" ]]; then
  N_GAMES=500 SEED=20260703 JAR="$JAR" bash scripts/forkcheck/run_forkcheck.sh "$FC" | tee -a "$OUT/queue.log"
  FC_PID=$(cat "$FC/run.pid")
  log "forkcheck detached pid=$FC_PID dir=$FC"
fi
NAME=b4vr CKPT="$CKPT" GAMES="$GAMES" WORKERS="$WORKERS" SERVERS=0 PORT=50082 JAR="$JAR" \
  ARMS="vrescue" FORGE_ARGS="" FORGE_ARGS_ACT="$RECIPE" \
  bash scripts/build3_surface_read.sh || { log "arm chain FAILED"; exit 1; }
RD=data/runs/build3-surface-read-b4vr
ARMS_VR=$(cat $RD/vrescue.done)
uv run python scripts/void_rescue_read.py $(echo "$ARMS_VR" | tr ',' ' ') --bar "$BAR" --out "$RD/void-rescue-read.json" \
  | tee "$RD/void-rescue-read.txt" | tee -a "$OUT/queue.log"
if [[ -n "$FC_PID" ]]; then
  until [ ! -d /proc/$FC_PID ] || { [ -f "$FC/results.jsonl" ] && [ "$(wc -l < "$FC/results.jsonl")" -ge 500 ]; }; do sleep 60; done
  uv run python scripts/forkcheck/compare.py "$FC" | tee "$FC/compare.txt" | tee -a "$OUT/queue.log"
  log "forkcheck done: $(grep -i "identical\|PASS\|FAIL" "$FC/compare.txt" | head -2 | tr '\n' ' ')"
fi
log "chain done"
echo OK > "$OUT/DONE"
