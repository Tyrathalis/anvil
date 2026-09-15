#!/usr/bin/env bash
# M12 Build 3 evening 5 (ADR-0106 C1): the PRIORITY slot's leaf calibration on
# heuristic games — the 09-11 pay-slot instrument moved to the first ply. Three
# heuristic-control arms (final_read.py --heuristic-control: no seat bridged,
# the searched heuristic seat named by -searchseats per seat run, the server
# serving anvil.value only) on the same pairs + seed base, the search directive
# observational (no -searchact), the first-ply copies under one leaf per arm
# (-searchleaf; every copy under a horizon leaf snapshots the certify axes):
#   next the Build 2 pin (the seat's next quiescent window; the head)
#   h2   the certify horizon (the head at a turn > t+2)
#   end  the copy to its natural end (the outcome; no head call)
# then scripts/prio_calibration.py joins the opts rows across arms per window
# (the mainline is byte-identical across arms; the rate draw is a seed hash, so
# the same windows are searched — the join rate is the proof) and reads per
# horizon: the candidate spread vs the roll sigma, rank agreement with next,
# the flip rate of the one-ply argmax, and the end arm's verdict on the flips.
#
# Runs off a SNAPSHOT jar (copied here; the tree may move under it). Detached
# by the caller (setsid nohup); watchd-registered; notifies on finish.
# Usage: build3_prio_calibration.sh
#   env: OUT (data/runs/build3-priocal), GAMES (200 per seat run), WORKERS (24),
#        SERVERS (2), PORT (50077), RATE (0.1: every candidate of a searched window
#        is a copy at the horizon, ~10x the pay slot's exposure), ROLLS (4), CLOCK
#        (2400 s), LEAVES ("next h2 end"), CKPT (the e3 build), JAR (source jar)
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
FORGE=/home/tyrathalis/Everything/Projects/forge
cd "$REPO"
OUT=${OUT:-$REPO/data/runs/build3-priocal}
case "$OUT" in /*) ;; *) OUT="$REPO/$OUT" ;; esac
mkdir -p "$OUT"
GAMES=${GAMES:-200}; WORKERS=${WORKERS:-24}; SERVERS=${SERVERS:-2}; PORT=${PORT:-50077}; CHUNK=${CHUNK:-9}  # 200 games / 9 = 23 chunks over 24 workers
RATE=${RATE:-0.1}; ROLLS=${ROLLS:-4}; CLOCK=${CLOCK:-2400}  # 2,400 s: bounds a pathological game (the eot arm: one seed ran 6,928 s of AI eval-thread timeouts under 7,200 and held the arm 4 h); sub rows are written per window, so a clipped game only loses its remaining windows
LEAVES=${LEAVES:-"next h2 end"}
CKPT=${CKPT:-data/training/m12-build3-e3/last.pt}
SRC_JAR=${JAR:-$(ls -t $FORGE/forge-gui-desktop/target/*jar-with-dependencies.jar | head -1)}
JAR="$OUT/forge-b3pcal.jar"
if [[ ! -f "$JAR" ]]; then
  cp "$SRC_JAR" "$JAR"
  git -C "$FORGE" rev-parse HEAD > "$OUT/forge-b3pcal.commit"
  sha256sum "$JAR" > "$OUT/forge-b3pcal.sha256"
fi
export PYTHONUNBUFFERED=1 DISPLAY=:0
export XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1)
LOG="$OUT/chain.log"
log() { echo "$(date -Iseconds) $*" | tee -a "$LOG"; }
state() { echo "{\"stage\":\"$1\",\"at\":\"$(date -Iseconds)\"}" >> "$OUT/stages.jsonl"; }
notify() { python3 -c "from anvil.training.notify import notify; notify('$1', '''$2''', tag='build3')"; }
python3 scripts/anvil_watchd.py register --name build3-priocal --pid $$ --dir "$REPO/data/runs" --stall-min 90
log "start jar=$JAR ($(cat $OUT/forge-b3pcal.commit)) ckpt=$CKPT games=$GAMES/seat workers=$WORKERS rate=$RATE rolls=$ROLLS clock=$CLOCK leaves='$LEAVES'"
state start
fail() { log "CALIBRATION CHAIN FAILED at $1"; state "failed-$1"; notify "anvil build3 priority-slot calibration FAILED" "$1 see $LOG"; python3 scripts/anvil_watchd.py unregister --name build3-priocal; exit 1; }
arms_of() { ls -dt data/runs/${1}arm-s0-* | head -1 | tr -d '\n'; echo -n ","; ls -dt data/runs/${1}arm-s1-* | head -1; }

for LEAF in $LEAVES; do
  if [[ -f "$OUT/$LEAF.done" ]]; then log "arm $LEAF: done already ($(cat $OUT/$LEAF.done))"; continue; fi
  state "arm-$LEAF"
  FARGS="-search -searchrate $RATE -searchrolls $ROLLS -searchleaf $LEAF -searchclock $CLOCK"
  log "arm $LEAF start fargs='$FARGS'"
  nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT" --name "b3pcal-$LEAF" --games "$GAMES" \
      --workers "$WORKERS" --servers "$SERVERS" --chunk "$CHUNK" --port "$PORT" --jar "$JAR" --skip-ante --heuristic-control --labels \
      --forge-args="$FARGS" >> "$OUT/$LEAF.log" 2>&1 || fail "$LEAF"
  arms_of "b3pcal-$LEAF" > "$OUT/$LEAF.done"
  log "arm $LEAF done: $(cat $OUT/$LEAF.done)"
done

state read
ARMS=()
for LEAF in $LEAVES; do ARMS+=(--arm "$LEAF=$(cat $OUT/$LEAF.done)"); done
uv run python scripts/prio_calibration.py "${ARMS[@]}" --out "$OUT/read.json" 2>&1 | tee "$OUT/read.md" | tee -a "$LOG" || fail read
state done
notify "anvil build3 priority-slot calibration DONE" "$(head -c 1500 $OUT/read.md)"
python3 scripts/anvil_watchd.py unregister --name build3-priocal
log "chain done"
