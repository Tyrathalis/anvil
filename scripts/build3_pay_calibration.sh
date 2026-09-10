#!/usr/bin/env bash
# M12 Build 3 evening 4 close (ADR-0105): the payment target's horizon
# CALIBRATION on heuristic games. Three heuristic-control arms (final_read.py
# --heuristic-control: no seat bridged, the searched heuristic seat named by
# -searchseats per seat run, the server serving anvil.value only) on the same
# pairs + seed base, the search directive observational (no -searchact), the
# pay slot ON (-searchpay B), one leaf per arm:
#   eot  the target (the head at the seat's first quiescent window of a later turn)
#   h2   the certify horizon (the head at a turn > t+2, + the axes snapshot)
#   end  the copy to its natural end (the outcome; no head call)
# then scripts/pay_calibration.py joins the sub rows across arms (the mainline
# is byte-identical across arms — the join rate is the proof) and reads the
# conversion of the eot leaf's positives by the rollout.
#
# Runs off a SNAPSHOT jar (copied here; the tree may move under it). Detached
# by the caller (setsid nohup); watchd-registered; notifies on finish.
# Usage: build3_pay_calibration.sh
#   env: OUT (data/runs/build3-paycal), GAMES (200 per seat run), WORKERS (16),
#        PORT (50077), RATE (0.25), ROLLS (4), B (2), CLOCK (7200 s: the searched
#        game's wall allowance under the rollout leaves), LEAVES ("eot h2 end"),
#        CKPT (the e3 build: the pool's own value head), JAR (source jar)
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
FORGE=/home/tyrathalis/Everything/Projects/forge
cd "$REPO"
OUT=${OUT:-$REPO/data/runs/build3-paycal}
case "$OUT" in /*) ;; *) OUT="$REPO/$OUT" ;; esac
mkdir -p "$OUT"
GAMES=${GAMES:-200}; WORKERS=${WORKERS:-16}; PORT=${PORT:-50077}; CHUNK=${CHUNK:-13}  # 200 games / 13 = 16 chunks: every worker busy (final_read's default 50 left 12 of 16 idle, 21:08 09-09)
RATE=${RATE:-0.25}; ROLLS=${ROLLS:-4}; B=${B:-2}; CLOCK=${CLOCK:-7200}
LEAVES=${LEAVES:-"eot h2 end"}
CKPT=${CKPT:-data/training/m12-build3-e3/last.pt}
SRC_JAR=${JAR:-$(ls -t $FORGE/forge-gui-desktop/target/*jar-with-dependencies.jar | head -1)}
JAR="$OUT/forge-b3cal.jar"
if [[ ! -f "$JAR" ]]; then
  cp "$SRC_JAR" "$JAR"
  git -C "$FORGE" rev-parse HEAD > "$OUT/forge-b3cal.commit"
  sha256sum "$JAR" > "$OUT/forge-b3cal.sha256"
fi
export PYTHONUNBUFFERED=1 DISPLAY=:0
export XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1)
LOG="$OUT/chain.log"
log() { echo "$(date -Iseconds) $*" | tee -a "$LOG"; }
state() { echo "{\"stage\":\"$1\",\"at\":\"$(date -Iseconds)\"}" >> "$OUT/stages.jsonl"; }
notify() { python3 -c "from anvil.training.notify import notify; notify('$1', '''$2''', tag='build3')"; }
python3 scripts/anvil_watchd.py register --name build3-paycal --pid $$ --dir "$REPO/data/runs" --stall-min 90
log "start jar=$JAR ($(cat $OUT/forge-b3cal.commit)) ckpt=$CKPT games=$GAMES/seat workers=$WORKERS rate=$RATE rolls=$ROLLS B=$B clock=$CLOCK leaves='$LEAVES'"
state start
fail() { log "CALIBRATION CHAIN FAILED at $1"; state "failed-$1"; notify "anvil build3 pay calibration FAILED" "$1 see $LOG"; python3 scripts/anvil_watchd.py unregister --name build3-paycal; exit 1; }
arms_of() { ls -dt data/runs/${1}arm-s0-* | head -1 | tr -d '\n'; echo -n ","; ls -dt data/runs/${1}arm-s1-* | head -1; }

for LEAF in $LEAVES; do
  if [[ -f "$OUT/$LEAF.done" ]]; then log "arm $LEAF: done already ($(cat $OUT/$LEAF.done))"; continue; fi
  state "arm-$LEAF"
  FARGS="-search -searchrate $RATE -searchrolls $ROLLS -searchpay $B -searchpayleaf $LEAF -searchclock $CLOCK"
  log "arm $LEAF start fargs='$FARGS'"
  nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT" --name "b3cal-$LEAF" --games "$GAMES" \
      --workers "$WORKERS" --chunk "$CHUNK" --port "$PORT" --jar "$JAR" --skip-ante --heuristic-control --labels \
      --forge-args="$FARGS" >> "$OUT/$LEAF.log" 2>&1 || fail "$LEAF"
  arms_of "b3cal-$LEAF" > "$OUT/$LEAF.done"
  log "arm $LEAF done: $(cat $OUT/$LEAF.done)"
done

state read
ARMS=()
for LEAF in $LEAVES; do ARMS+=(--arm "$LEAF=$(cat $OUT/$LEAF.done)"); done
uv run python scripts/pay_calibration.py "${ARMS[@]}" --out "$OUT/read.json" 2>&1 | tee "$OUT/read.md" | tee -a "$LOG" || fail read
state done
notify "anvil build3 pay calibration DONE" "$(head -c 1500 $OUT/read.md)"
python3 scripts/anvil_watchd.py unregister --name build3-paycal
log "chain done"
