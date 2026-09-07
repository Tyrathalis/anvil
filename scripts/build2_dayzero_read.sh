#!/usr/bin/env bash
# M12 Build 2 — THE ONE GATE: the day-zero paired read (m12-plan Build 2;
# ADR-0101 §3 items 2/4/5; the instrument decision of 09-06 s6: the standard
# 2,000-game read vs the heuristic, arms paired game-by-game on the final_read
# pairs file + seed base, NOT the fork-window sched read).
#
# Arms (each = final_read.py: 2 x 1,000 games, seats 0/1 bridged in turn, argmax
# serve, -reask, no Ante pass — the paired diffs read raw wins):
#   ref     iter-019 alone, re-read on the Build 2 jar (the boundary changed the
#           game path; never compare winrates across eras)
#   dz      the day-zero ckpt alone (policy drift check: expected ~0 vs ref)
#   dzla    the day-zero ckpt + lookahead: -search -searchrate 1 -searchrolls 1
#           -searchact 0.05 -searchtemp 0.025 (the acting rule ON; the bar from
#           the 09-06 smoke's margin distribution, ADR-0103 addendum)
#   dzla10  the same at -searchact 0.10 (the bracket's second bar; BARS env)
# Gate: dzla − dz >= +1.5pp GO / <= 0 KILL-CANDIDATE / in-band proceeds (the big
# run then needs a post-Build-4 read >= +1.5pp). The heuristic + lookahead
# control arms follow on their own jar commit (scripts/build2_control_read.sh).
#
# The jar is SNAPSHOTTED into the read dir so the fork can rebuild while the
# arms are in flight (the harness verifies the jar sha per worker launch).
# Launch (the detached-run checklist): setsid nohup, watchd-registered, notify
# on completion/failure, PYTHONUNBUFFERED. Usage: build2_dayzero_read.sh
#   env: NAME (b2), BARS ("0.05 0.10"), TEMP (0.025), GAMES (1000 per seat),
#        WORKERS (8), CKPT_REF, CKPT_DZ, JAR, PORT (50065)
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
FORGE=/home/tyrathalis/Everything/Projects/forge
cd "$REPO"
NAME=${NAME:-b2}
BARS=${BARS:-"0.05 0.10"}
TEMP=${TEMP:-0.025}
GAMES=${GAMES:-1000}
WORKERS=${WORKERS:-8}
PORT=${PORT:-50065}
CKPT_REF=${CKPT_REF:-data/training/d6-run11/iter-019/train/last.pt}
CKPT_DZ=${CKPT_DZ:-data/training/m12-build1-stopstate/last.pt}
OUT=data/runs/build2-dayzero
mkdir -p "$OUT"
SRC_JAR=${JAR:-$(ls -t $FORGE/forge-gui-desktop/target/*jar-with-dependencies.jar | head -1)}
JAR="$OUT/forge-build2.jar"
if [[ ! -f "$JAR" ]]; then
  cp "$SRC_JAR" "$JAR"
  git -C "$FORGE" rev-parse HEAD > "$OUT/forge-build2.commit"
  sha256sum "$JAR" > "$OUT/forge-build2.sha256"
fi
export PYTHONUNBUFFERED=1 DISPLAY=:0
export XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1)
LOG="$OUT/chain.log"
log() { echo "$(date -Iseconds) $*" | tee -a "$LOG"; }
state() { echo "{\"stage\":\"$1\",\"at\":\"$(date -Iseconds)\"}" >> "$OUT/stages.jsonl"; }
python3 scripts/anvil_watchd.py register --name build2-dayzero --pid $$ --dir "$REPO/data/runs" --stall-min 60
log "chain start jar=$SRC_JAR -> $JAR bars=[$BARS] temp=$TEMP games=$GAMES/seat"

# newest pair of arm dirs for a read name
arms_of() { ls -dt data/runs/${1}arm-s0-* | head -1 | tr -d '\n'; echo -n ","; ls -dt data/runs/${1}arm-s1-* | head -1; }

run_arm() { # tag ckpt [forge-args]
  local tag=$1 ckpt=$2 fargs=${3:-}
  if [[ -f "$OUT/$tag.done" ]]; then log "arm $tag: done already ($(cat $OUT/$tag.done))"; return 0; fi
  state "arm-$tag-start"
  local extra=()
  if [[ -n "$fargs" ]]; then extra=(--forge-args "$fargs" --labels); fi
  nice -n 19 uv run python scripts/final_read.py --ckpt "$ckpt" --name "$NAME-$tag" --games "$GAMES" \
      --workers "$WORKERS" --port "$PORT" --jar "$JAR" --skip-ante "${extra[@]}" >> "$OUT/$tag.log" 2>&1
  local rc=$?
  if [[ $rc -ne 0 ]]; then log "arm $tag FAILED rc=$rc"; state "arm-$tag-failed"; return $rc; fi
  arms_of "$NAME-$tag" > "$OUT/$tag.done"
  log "arm $tag done: $(cat $OUT/$tag.done)"; state "arm-$tag-done"
}

fail() { log "CHAIN FAILED at $1"; python3 -c "from anvil.training.notify import notify; notify('anvil build2 day-zero read FAILED', '$1', tag='build2')"; python3 scripts/anvil_watchd.py unregister --name build2-dayzero; exit 1; }

run_arm ref "$CKPT_REF" || fail ref
run_arm dz "$CKPT_DZ" || fail dz
ARMS=(--arm "ref=$(cat $OUT/ref.done)" --arm "dz=$(cat $OUT/dz.done)")
first=1
for bar in $BARS; do
  tag="dzla$(echo $bar | sed 's/0\.//')"
  run_arm "$tag" "$CKPT_DZ" "-search -searchrate 1 -searchrolls 1 -searchact $bar -searchtemp $TEMP" || fail "$tag"
  if [[ $first -eq 1 ]]; then ARMS+=(--arm "dzla=$(cat $OUT/$tag.done)"); first=0; else ARMS+=(--arm "$tag=$(cat $OUT/$tag.done)"); fi
done
state "read-start"
uv run python scripts/build2_read.py arms "${ARMS[@]}" --out "$OUT/read.json" | tee -a "$LOG"
state "read-done"
VERDICT=$(python3 -c "import json;print(json.load(open('$OUT/read.json'))['verdict'])")
python3 -c "from anvil.training.notify import notify; notify('anvil build2 day-zero read complete', '''$VERDICT''', tag='build2')"
python3 scripts/anvil_watchd.py unregister --name build2-dayzero
log "chain done: $VERDICT"
