#!/usr/bin/env bash
# M12 Build 3 — the surface-label run (m12-plan Build 3; ADR-0103 enumerators,
# ADR-0104 acting rule). The sub-row pool the answer-shape decoder distills
# from: bridged SELF-PLAY on the day-zero ckpt (both seats searched), every
# quiescent main-phase window searched at rate 1 / rolls 1, the surface
# expansion round ON (-searchsurf B, one copy per enumerated answer of the
# first traced surface on the top-B candidates' paths -> `sub` rows with
# per-answer leaf values), the acting rule ON at the pinned shakedown bar
# (0.10, ADR-0104 addendum) so the labels sit on the behavior distribution.
# The obs store (sv=3, named surface opts + the heuristic's answers) doubles
# as imitation labels; census + labels.jsonl per worker.
#
# Runs from a worktree pinned to a commit (the tree it imports from must not
# be edited under it — memory: no-tree-edits-during-training-runs); the jar
# is SNAPSHOTTED into the run dir. Detached-run checklist: setsid nohup by the
# caller, watchd-registered here, unregister + notify inside this wrapper.
# Usage: build3_surface_labels.sh
#   env: WT (worktree), NAME (b3-surflab), OUT (run-chain dir), GAMES (1000), WORKERS (8), PORT (50075), BAR (0.10),
#        TEMP (0.025), RATE (1), SURF (2), CAP (8), SEED (20260908), CKPT, JAR
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
WT=${WT:-/home/tyrathalis/Everything/Projects/anvil-wt-b3label}
FORGE=/home/tyrathalis/Everything/Projects/forge
NAME=${NAME:-b3-surflab}
GAMES=${GAMES:-1000}; WORKERS=${WORKERS:-8}; PORT=${PORT:-50075}
BAR=${BAR:-0.10}; TEMP=${TEMP:-0.025}; RATE=${RATE:-1}; SURF=${SURF:-2}; CAP=${CAP:-8}
SEED=${SEED:-20260908}
ROLLS=${ROLLS:-1}  # leaf rolls per copy (2 = a roll pair per answer, the leaf-noise estimate)
# evening 4 (ADR-0105): the payment expansion slot (-searchpay B, its own slot
# beside the surface slot), its leaf (eot = the seat's first quiescent window
# of a later turn; next = fork A's), -paytelemetry (the resolution-effect
# census row), and the server's tag list (TAGS; empty = the ckpt's full set —
# the pay tag WITHHELD on the mainline for the pay pool: the natural line is
# auto, the head is untrained, and copies never bridge it under the gate)
PAY=${PAY:-0}; PAYLEAF=${PAYLEAF:-eot}; PAYTEL=${PAYTEL:-0}; TAGS=${TAGS:-}
# the searched game's wall allowance (-searchclock; empty = the jar's 900 s default) — a rollout
# pay leaf (h<N> / end) plays heavier copies; 2,400 s bounds a pathological game (09-10)
CLOCK=${CLOCK:-}
DEADLINE_MS=${DEADLINE_MS:-20000}
CKPT=${CKPT:-data/training/m12-build1-stopstate/last.pt}
OUT=${OUT:-$REPO/data/runs/build3-surface-labels}
mkdir -p "$OUT"
SRC_JAR=${JAR:-$(ls -t $FORGE/forge-gui-desktop/target/*jar-with-dependencies.jar | head -1)}
JAR="$OUT/forge-b3.jar"
if [[ ! -f "$JAR" ]]; then
  cp "$SRC_JAR" "$JAR"
  git -C "$FORGE" rev-parse HEAD > "$OUT/forge-b3.commit"
  sha256sum "$JAR" > "$OUT/forge-b3.sha256"
fi
export PYTHONUNBUFFERED=1 DISPLAY=:0
# Eight workers hitting their first windows together with the expansion round
# (B=2, cap 8 -> up to 16 extra copies per window, each asking the bridge) pushed
# an ask past the bridge's 5 s default at the first launch (09-07 14:42: every
# game poisoned at turn 1; the same seed plays clean single-worker) -> the
# worker deadline is raised for this run (orchestrator ANVIL_EXTRA_JVM_OPTS).
export ANVIL_EXTRA_JVM_OPTS="-Danvil.bridge.deadline.ms=$DEADLINE_MS"
export XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1)
LOG="$OUT/chain.log"
log() { echo "$(date -Iseconds) $*" | tee -a "$LOG"; }
state() { echo "{\"stage\":\"$1\",\"at\":\"$(date -Iseconds)\"}" >> "$OUT/stages.jsonl"; }
cd "$WT"
FARGS="-search -searchrate $RATE -searchrolls $ROLLS -searchsurf $SURF -searchsurfcap $CAP -searchact $BAR -searchtemp $TEMP"
[[ "$PAY" != "0" ]] && FARGS="$FARGS -searchpay $PAY -searchpayleaf $PAYLEAF"
[[ "$PAYTEL" != "0" ]] && FARGS="$FARGS -paytelemetry"
[[ -n "$CLOCK" ]] && FARGS="$FARGS -searchclock $CLOCK"
SERVER_EXTRA=()
[[ -n "$TAGS" ]] && SERVER_EXTRA+=(--tags "$TAGS")
python3 "$REPO/scripts/anvil_watchd.py" register --name "build3-$NAME" --pid $$ --dir "$REPO/data/runs" --stall-min 60
log "start wt=$WT ($(git -C "$WT" rev-parse --short HEAD)) jar=$SRC_JAR -> $JAR ($(cat $OUT/forge-b3.commit)) ckpt=$CKPT games=$GAMES workers=$WORKERS deadline_ms=$DEADLINE_MS fargs='$FARGS'"
state start

notify() { python3 -c "from anvil.training.notify import notify; notify('$1', '$2', tag='build3')"; }
finish() { # rc
  python3 "$REPO/scripts/anvil_watchd.py" unregister --name "build3-$NAME"
  if [[ $1 -eq 0 ]]; then notify "anvil build3 surface-label run DONE" "$OUT"; else notify "anvil build3 surface-label run FAILED" "rc=$1 see $LOG"; fi
  exit $1
}

uv run python -m anvil.bridge.server --mode model --ckpt "$CKPT" --port $PORT --pass-delta 0 "${SERVER_EXTRA[@]}" \
  > "$OUT/server.log" 2>&1 &
SERVER=$!
for i in $(seq 1 300); do (echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null && break; sleep 2; done
(echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null || { log "server never opened port"; kill $SERVER; state server-failed; finish 1; }
log "server up pid=$SERVER"
state generate-start
t0=$(date +%s)
nice -n 19 uv run python -m anvil.bridge.harness launch --pool --games "$GAMES" --games-per-pair 5 \
    --workers "$WORKERS" --chunk 50 --bridge "grpc:localhost:$PORT" --obs --census --labels --reask \
    --purpose "$NAME" --seed-base "$SEED" --jar "$JAR" --heap 3g --forge-args "$FARGS" \
    >> "$OUT/harness.log" 2>&1
rc=$?; t1=$(date +%s)
log "harness rc=$rc wall=$((t1-t0))s"
kill -TERM $SERVER 2>/dev/null; sleep 5; kill -KILL $SERVER 2>/dev/null
RUN=$(ls -dt "$REPO"/data/runs/${NAME}-* 2>/dev/null | head -1)
echo "{\"games\":$GAMES,\"rolls\":$ROLLS,\"bar\":$BAR,\"temp\":$TEMP,\"rate\":$RATE,\"surf\":$SURF,\"cap\":$CAP,\"pay\":$PAY,\"payleaf\":\"$PAYLEAF\",\"tags\":\"$TAGS\",\"rc\":$rc,\"wall_s\":$((t1-t0)),\"run\":\"$RUN\"}" > "$OUT/DONE"
state "generate-done rc=$rc"
finish $rc
