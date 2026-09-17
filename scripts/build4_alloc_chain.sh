#!/usr/bin/env bash
# Build 4 (ADR-0109 item 2; 09-17): the allocation head's chain, unattended —
#   1. the forkcheck of the alloc tip (flag off = byte-identical: no ask, no scan)
#   2. THE POST-BUILD-4 READ (the Build 2 gate's second reading, ADR-0104): three
#      arms on the served build + the fitted allocation head, 2 x GAMES games each
#      vs the heuristic on the final_read pairs, 24 x 2:
#        on     the build alone (network alone, greedy)
#        act    the build + the recipe (rate 1, rolls 2, surfaces + surface acting at 0.10)
#        alloc  the same recipe under the allocation head (-searchalloc TAU -searchfloor FLOOR)
#      Gate: act − on >= +1.5pp clears the big run's launch condition; alloc − act
#      within noise at a lower call count = the head's strength-neutrality check
#      (its verdict is the shakedown's equal-box-time arm, not this).
#   3. read.json (on = the reference) + read-alloc.json (act = the reference)
# Launch: uv run python -m anvil.runs launch --name build4-alloc-chain --dir data/runs/build4-alloc -- bash scripts/build4_alloc_chain.sh
#   env: CKPT (the alloc-fitted build), TAU (from its alloc_fit record), FLOOR (0.1), GAMES (1000 / seat),
#        WORKERS (24), SKIP_FORKCHECK (unset)
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/build4-alloc; mkdir -p "$OUT"
JAR=$OUT/forge-alloc.jar; FC=$REPO/data/forkcheck/run-20260917-build4-alloc
CKPT=${CKPT:-data/training/m12-build4-e1a/last.pt}
TAU=${TAU:-$(uv run python -c "import torch,sys;print(torch.load('$CKPT',map_location='cpu',weights_only=False)['config']['alloc_fit']['tau'])")}
FLOOR=${FLOOR:-0.1}; GAMES=${GAMES:-1000}; WORKERS=${WORKERS:-24}
RECIPE="-search -searchrate 1 -searchrolls 2 -searchsurf 2 -searchsurfcap 8 -searchact 0.10 -searchtemp 0.025 -searchactkinds entity_one,entity_set,mode"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "chain start jar=$JAR ($(cat $OUT/forge-alloc.commit)) ckpt=$CKPT tau=$TAU floor=$FLOOR games=$GAMES/seat workers=$WORKERS"
if [[ -z "${SKIP_FORKCHECK:-}" && ! -f "$FC/compare.txt" ]]; then
  N_GAMES=500 SEED=20260703 JAR="$JAR" bash scripts/forkcheck/run_forkcheck.sh "$FC" | tee -a "$OUT/queue.log"
  pid=$(cat "$FC/run.pid"); until [ ! -d /proc/$pid ] || { [ -f "$FC/results.jsonl" ] && [ "$(wc -l < "$FC/results.jsonl")" -ge 500 ]; }; do sleep 60; done
  uv run python scripts/forkcheck/compare.py "$FC" | tee "$FC/compare.txt" | tee -a "$OUT/queue.log"
  log "forkcheck done: $(grep -i "identical\|PASS\|FAIL" "$FC/compare.txt" | head -2 | tr '\n' ' ')"
fi
NAME=b4post CKPT="$CKPT" GAMES="$GAMES" WORKERS="$WORKERS" SERVERS=0 PORT=50068 JAR="$JAR" \
  ARMS="on act alloc" FORGE_ARGS="" FORGE_ARGS_ACT="$RECIPE" FORGE_ARGS_ALLOC="$RECIPE -searchalloc $TAU -searchfloor $FLOOR" \
  bash scripts/build3_surface_read.sh || { log "read chain FAILED"; exit 1; }
RD=data/runs/build3-surface-read-b4post
ARMS_ON=$(cat $RD/on.done); ARMS_ACT=$(cat $RD/act.done); ARMS_ALLOC=$(cat $RD/alloc.done)
uv run python scripts/build2_read.py arms --arm "on=$ARMS_ON" --arm "act=$ARMS_ACT" --arm "alloc=$ARMS_ALLOC" --out "$RD/read.json" | tee -a "$OUT/queue.log"
uv run python scripts/build2_read.py arms --arm "act=$ARMS_ACT" --arm "alloc=$ARMS_ALLOC" --out "$RD/read-alloc.json" | tee -a "$OUT/queue.log"
uv run python scripts/alloc_smoke_read.py $(echo "$ARMS_ALLOC" | tr ',' ' ') | tee "$RD/alloc-census.txt" | tee -a "$OUT/queue.log"
log "chain done"
echo OK > "$OUT/DONE"
