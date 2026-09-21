#!/usr/bin/env bash
# 09-21 (pre-shakedown prep), unattended, behind the census bundle's forkcheck:
#   1. wait for data/forkcheck/run-20260921-build4-census/compare.txt (a quiet box);
#   2. THE SHALLOW-WIDE BENCH CELL: 24 x 2, 64 games, the served build, the shallow-wide
#      recipe (rate 1, rolls 1, the next leaf, no surface expansion, the acting rule) — the
#      third shape's g/h for the shakedown's equal-box-time split (recipe 347, deep x2.83 known);
#   3. THE CONTENTION SMOKE: a synthetic foreign GPU job (scripts/gpu_burner.py under setsid,
#      6 min) beside a 4-game recipe smoke (4 workers x 1 server) -> contention_read.py:
#      games by status, deadline / poison lines, per-game wall vs the 11:19 census smoke.
# Launch: uv run python -m anvil.runs launch --name build4-prep-chain --dir data/runs/build4-prep \
#           --watch 'data/runs/b4prep-*' --watch 'data/runs/b4cont-*' --watch 'data/runs/build3-surface-read-b4cont' \
#           -- bash scripts/build4_prep_chain.sh
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/build4-prep; mkdir -p "$OUT"
JAR=$REPO/data/runs/build4-census/forge-census.jar; FC=$REPO/data/forkcheck/run-20260921-build4-census
CKPT=data/training/m12-build4-e1a/last.pt
SHALLOW="-search -searchrate 1 -searchrolls 1 -searchact 0.10 -searchtemp 0.025"
RECIPE="-search -searchrate 1 -searchrolls 2 -searchsurf 2 -searchsurfcap 8 -searchact 0.10 -searchtemp 0.025 -searchactkinds entity_one,entity_set,mode"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "prep chain start; waiting for $FC/compare.txt"
until [ -f "$FC/compare.txt" ]; do sleep 60; touch "$OUT/waiting"; done
log "forkcheck: $(grep -i "identical\|PASS\|FAIL" "$FC/compare.txt" | head -1)"
if [[ ! -f "$OUT/bench.done" ]]; then
  uv run python scripts/fleet_bench.py --jar "$JAR" --ckpt "$CKPT" --cells 24:2 --games 64 --port 50090 \
    --name b4prep-bench-shallow --forge-args="$SHALLOW" >> "$OUT/bench-shallow.log" 2>&1 || { log "shallow cell FAILED"; exit 1; }
  cp data/runs/b4prep-bench-shallow/bench.md "$OUT/bench-shallow.md" 2>/dev/null; echo ok > "$OUT/bench.done"
  log "shallow cell: $(tail -2 "$OUT/bench-shallow.md" 2>/dev/null | tr '\n' ' ')"
fi
log "contention smoke: burner (setsid, 360 s) + 4-game recipe smoke"
setsid nohup uv run python scripts/gpu_burner.py --seconds 360 > "$OUT/burner.log" 2>&1 < /dev/null &
sleep 20
NAME=b4cont CKPT="$CKPT" GAMES=2 WORKERS=4 SERVERS=1 PORT=50085 JAR="$JAR" ARMS="act" FORGE_ARGS="" FORGE_ARGS_ACT="$RECIPE" \
  bash scripts/build3_surface_read.sh || log "contention smoke arm FAILED (read what it left)"
ARMS_C=$(cat data/runs/build3-surface-read-b4cont/act.done 2>/dev/null | tr ',' ' ')
ARMS_R=$(cat data/runs/build3-surface-read-b4cen/act.done | tr ',' ' ')
uv run python scripts/contention_read.py $ARMS_C --ref $ARMS_R --out "$OUT/contention-read.json" | tee -a "$OUT/queue.log"
log "burner: $(tail -1 "$OUT/burner.log")"
log "prep chain done"
echo OK > "$OUT/DONE"
