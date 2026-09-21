#!/usr/bin/env bash
# ADR-0115 (09-21): THE SHAKEDOWN — four search-shape arms at EQUAL BOX TIME, sequential, each a
# selfplay.py loop from the day-zero build (m12-build4-e1a) on the pinned jar, the run of record's
# loop settings (480 games/iter, lr 1e-5, replay 4 @ 0.33, KL 0.06, the ADR-0113 search terms),
# 24 workers x 2 servers, drills OFF, no per-arm day-zero read; each arm closes with the 2,000-game
# read vs the heuristic (1,000 / seat, network alone) -> read.md. Arm order: recipe, alloc, shallow, deep.
# Launch: uv run python -m anvil.runs launch --name shakedown --dir data/runs/shakedown --resume-on-gone \
#           --watch 'data/training/shakedown-*' --watch 'data/runs/shakedown-*' --watch 'data/runs/sd*' \
#           --stall-min 180 -- bash scripts/shakedown_chain.sh
#   env: WALL_HOURS (30), ARMS ("recipe alloc shallow deep"), JAR, CKPT, WORKERS (24), READ_GAMES (1000 / seat)
# Pause / resume (a maintenance reboot): anvil.runs pause --name shakedown --wait ... anvil.runs relaunch --name shakedown
# (the loop resumes its iteration + wall budget from loop_state.json; a finished arm is skipped by its marker).
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/shakedown; mkdir -p "$OUT"
JAR=${JAR:-$REPO/data/runs/build4-census/forge-census.jar}
CKPT=${CKPT:-data/training/m12-build4-e1a/last.pt}
WALL_HOURS=${WALL_HOURS:-30}; ARMS=${ARMS:-recipe alloc shallow deep}; WORKERS=${WORKERS:-24}; READ_GAMES=${READ_GAMES:-1000}
RECIPE="-search -searchrate 1 -searchrolls 2 -searchsurf 2 -searchsurfcap 8 -searchact 0.10 -searchtemp 0.025 -searchactkinds entity_one,entity_set,mode"
SHALLOW="-search -searchrate 1 -searchrolls 1 -searchact 0.10 -searchtemp 0.025"
DEEP="$RECIPE -searchdeep 3 -searchdeepleaf h2 -searchdeeprolls 4 -searchdeeplo 0.02 -searchdeepfloor 0.1 -searchclock 3600"  # = the priced bench arm (build3_deep_queue.sh DEEPARGS)
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
[[ -f "$OUT/read.md" ]] || printf '# The shakedown (ADR-0115) — per-arm reads\n\n| arm | wall h | iterations | games | final ckpt | 2,000-game read (network alone) | last lookahead arm |\n|---|---|---|---|---|---|---|\n' > "$OUT/read.md"
log "shakedown chain start jar=$JAR ckpt=$CKPT wall=${WALL_HOURS}h/arm arms='$ARMS'"
for arm in $ARMS; do
  case $arm in
    recipe) FARGS="$RECIPE"; ALLOC=off ;;
    alloc) FARGS="$RECIPE"; ALLOC=head ;;
    shallow) FARGS="$SHALLOW"; ALLOC=off ;;
    deep) FARGS="$DEEP"; ALLOC=off ;;
    *) log "unknown arm $arm"; exit 1 ;;
  esac
  NAME=shakedown-$arm; LOOP=data/training/$NAME
  if [[ -f "$OUT/$arm.done" ]]; then log "arm $arm done already"; continue; fi
  if [[ ! -f "$LOOP/WALL-STOP" && ! -f "$LOOP/LOOP-COMPLETE" ]]; then
    log "arm $arm: loop (resumes from $LOOP/loop_state.json if present)"
    uv run python -m anvil.training.selfplay --name "$NAME" --ckpt "$CKPT" --iterations 200 --wall-hours "$WALL_HOURS" \
      --games 480 --games-per-pair 2 --workers "$WORKERS" --chunk 30 --port 50063 --seed-base 20260921 \
      --temperature 1.0 --replay 4 --fresh-weight 1.0 --replay-weight 0.33 --rl-workers 12 --epochs 1 --lr 1e-5 \
      --ent-weight 0.003 --ent-floor 0.08 --rl-seg 128 --guard-kl 0.06 --guard-ent-mult 2.0 --guard-veto-mult 1.5 \
      --guard-casts-floor 0.8 --penalty 0.02 --heur-frac 0.5 --value-weight 0.5 --traj-per-step 4 \
      --arms-every 5 --arms-pairs data/runs/d5arm-d0-s0-20260714-143546/pairs.txt --arms-games 200 --arms-seed-base 20260710 \
      --reask --jar "$JAR" --search-recipe "$FARGS" --search-alloc "$ALLOC" --search-floor 0.1 \
      --distill-carry-w --alloc-carry-w >> "$OUT/$arm.loop.log" 2>&1
    rc=$?
    if [[ -f "$LOOP/STOP" ]]; then log "arm $arm paused (STOP present) — exiting the chain; relaunch resumes"; exit 0; fi
    if [[ $rc -ne 0 && ! -f "$LOOP/WALL-STOP" ]]; then log "arm $arm loop FAILED rc=$rc"; exit 1; fi
    [[ -f "$LOOP/WALL-STOP" ]] || echo "$(date -Iseconds) iterations exhausted" > "$LOOP/LOOP-COMPLETE"
  fi
  FINAL=$(python3 -c "import json; print(json.load(open('$LOOP/loop_state.json'))['ckpt'])")
  ITERS=$(python3 -c "import json; print(json.load(open('$LOOP/loop_state.json'))['iteration'])")
  WALL=$(python3 -c "import json; print(round(json.load(open('$LOOP/loop_state.json')).get('wall_used_s',0)/3600,1))")
  if [[ ! -f "$OUT/$arm.read.done" ]]; then
    log "arm $arm: the 2,000-game read on $FINAL (network alone, $READ_GAMES / seat, $WORKERS x 2)"
    nice -n 19 uv run python scripts/final_read.py --ckpt "$FINAL" --name "sd-$arm" --games "$READ_GAMES" --workers "$WORKERS" \
      --port 50086 --servers 0 --jar "$JAR" --skip-ante >> "$OUT/$arm.read.log" 2>&1 || { log "arm $arm read FAILED"; exit 1; }
    ls -dt data/runs/sd-${arm}arm-s0-* | head -1 | tr -d '\n' > "$OUT/$arm.read.done"; echo -n "," >> "$OUT/$arm.read.done"; ls -dt data/runs/sd-${arm}arm-s1-* | head -1 >> "$OUT/$arm.read.done"
  fi
  READ=$(uv run python scripts/arms_report.py --arm "$arm=$(cat $OUT/$arm.read.done)" --out "$OUT/$arm.read.json" 2>/dev/null | grep -o "winrate [0-9.]* ± [0-9.]*" | head -1)
  LA=$(python3 -c "
import json,glob
fs=sorted(glob.glob('$LOOP/iter-*/arms-report.json'))
r=json.load(open(fs[-1])) if fs else {}
print(', '.join(f'{k} {v:.3f}' if isinstance(v,(int,float)) else f'{k} {v}' for k,v in r.items()) or 'n/a', fs[-1].split('/')[-2] if fs else '')" 2>/dev/null | cut -c1-120)
printf '| %s | %s | %s | %s | %s | %s | %s |\n' "$arm" "$WALL" "$ITERS" "$((ITERS*480))" "$FINAL" "$READ" "$LA" >> "$OUT/read.md"
echo ok > "$OUT/$arm.done"; log "arm $arm CLOSED: $READ"
done
log "shakedown chain done"; echo OK > "$OUT/DONE"
