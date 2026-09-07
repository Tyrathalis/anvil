#!/usr/bin/env bash
# M12 Build 2 — the heuristic CONTROL arms (ADR-0104 item 5; ADR-0101 §3 item 5):
#   heur    the heuristic mirror — no seat bridged, the read seat (s0 / s1 in
#           turn) named by -searchseats but no -search: the 50% symmetry check
#   heurla  heuristic + lookahead — the same seat searched and acted for with
#           the masked head's leaf values (the network never plays a decision)
# on the SAME jar snapshot as the day-zero arms (data/runs/build2-dayzero/
# forge-build2.jar) unless JAR names the control-commit jar after its
# forkcheck. Reads against the day-zero arms (build2_read.py arms). Runs after
# the day-zero chain (never concurrently: micro-batch composition drift).
# Usage: build2_control_read.sh   env: NAME (b2), BAR (0.05), TEMP (0.025), GAMES,
#        WORKERS, JAR, PORT (50065), CKPT (the day-zero ckpt: the head serving leaves)
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
cd "$REPO"
NAME=${NAME:-b2}; BAR=${BAR:-0.05}; TEMP=${TEMP:-0.025}; GAMES=${GAMES:-1000}; WORKERS=${WORKERS:-8}; PORT=${PORT:-50065}
CKPT=${CKPT:-data/training/m12-build1-stopstate/last.pt}
DZ=data/runs/build2-dayzero
OUT=data/runs/build2-control
mkdir -p "$OUT"
JAR=${JAR:-$DZ/forge-build2.jar}
export PYTHONUNBUFFERED=1 DISPLAY=:0
export XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1)
LOG="$OUT/chain.log"
log() { echo "$(date -Iseconds) $*" | tee -a "$LOG"; }
python3 scripts/anvil_watchd.py register --name build2-control --pid $$ --dir "$REPO/data/runs" --stall-min 60
log "control chain start jar=$JAR bar=$BAR temp=$TEMP"
arms_of() { ls -dt data/runs/${1}arm-s0-* | head -1 | tr -d '\n'; echo -n ","; ls -dt data/runs/${1}arm-s1-* | head -1; }
run_arm() { # tag [forge-args]
  local tag=$1 fargs=${2:-}
  if [[ -f "$OUT/$tag.done" ]]; then log "arm $tag: done already"; return 0; fi
  local extra=(--heuristic-control)
  if [[ -n "$fargs" ]]; then extra+=(--forge-args "$fargs" --labels); fi
  nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT" --name "$NAME-$tag" --games "$GAMES" \
      --workers "$WORKERS" --port "$PORT" --jar "$JAR" --skip-ante "${extra[@]}" >> "$OUT/$tag.log" 2>&1 || return 1
  arms_of "$NAME-$tag" > "$OUT/$tag.done"; log "arm $tag done: $(cat $OUT/$tag.done)"
}
fail() { log "CONTROL CHAIN FAILED at $1"; python3 -c "from anvil.training.notify import notify; notify('anvil build2 control read FAILED', '$1', tag='build2')"; python3 scripts/anvil_watchd.py unregister --name build2-control; exit 1; }
run_arm heur || fail heur
run_arm heurla "-search -searchrate 1 -searchrolls 1 -searchact $BAR -searchtemp $TEMP" || fail heurla
ARMS=()
for t in ref dz dzla dzla10; do
  f="$DZ/$t.done"; [[ -f "$f" ]] || f="$DZ/dzla05.done"
  if [[ -f "$DZ/$t.done" ]]; then ARMS+=(--arm "$t=$(cat $DZ/$t.done)"); elif [[ $t == dzla && -f $DZ/dzla05.done ]]; then ARMS+=(--arm "dzla=$(cat $DZ/dzla05.done)"); fi
done
ARMS+=(--arm "heur=$(cat $OUT/heur.done)" --arm "heurla=$(cat $OUT/heurla.done)")
uv run python scripts/build2_read.py arms "${ARMS[@]}" --out "$OUT/read.json" | tee -a "$LOG"
VERDICT=$(python3 -c "import json;print(json.load(open('$OUT/read.json'))['verdict'])")
python3 -c "from anvil.training.notify import notify; notify('anvil build2 control read complete', '''$VERDICT''', tag='build2')"
python3 scripts/anvil_watchd.py unregister --name build2-control
log "control chain done: $VERDICT"
