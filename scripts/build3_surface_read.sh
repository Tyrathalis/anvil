#!/usr/bin/env bash
# M12 Build 3 (ADR-0105): an evening's paired read — the fitted surface ckpt
# with the evening's surface tags SERVED vs the same ckpt with the server
# withholding them (the heuristic answers the surfaces), 2 x GAMES games per
# arm vs the heuristic on the final_read pairs + seeds, network alone (no
# search). The "nothing broke" read: no new crash class, misses counted,
# strength within noise (+ the per-tag census shares). Paired diff by
# scripts/build2_read.py arms (the first arm is the reference).
# Usage: build3_surface_read.sh   env: NAME (b3e1), CKPT, GAMES (300), WORKERS (8),
#        PORT (50066), JAR (snapshot source), TAGS_OFF (the server's tag list without surfaces),
#        ARMS (evening 4: "off on" default; "off on rescue" adds the third rung — the on arm
#        under FORGE_ARGS_RESCUE, default "-payrescue": the ADR-0102 rescue class admitted + paid
#        directed, the flag-gated bundle read on the same reference; evening 5: "on act" = the served
#        set under the search recipe in FORGE_ARGS vs the same + FORGE_ARGS_ACT, surface acting),
#        FORGE_ARGS (every arm)
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
FORGE=/home/tyrathalis/Everything/Projects/forge
cd "$REPO"
NAME=${NAME:-b3e1}
CKPT=${CKPT:-data/training/m12-build3-e1/last.pt}
GAMES=${GAMES:-300}; WORKERS=${WORKERS:-8}; PORT=${PORT:-50066}; SERVERS=${SERVERS:-0}  # 0 = ceil(WORKERS/12)
TAGS_OFF=${TAGS_OFF:-mtg.priority,mtg.mulligan_keep,mtg.trigger,mtg.binary,mtg.number,mtg.attack,mtg.block,mtg.pay_mana_class}
ARMS=${ARMS:-off on}; FORGE_ARGS=${FORGE_ARGS:-}; FORGE_ARGS_RESCUE=${FORGE_ARGS_RESCUE:--payrescue}
SERVER_ARGS=${SERVER_ARGS:-}  # evening 4: e.g. "--pay-bar 0.2" (every arm's server)
FORGE_ARGS_ACT=${FORGE_ARGS_ACT:--searchactkinds mode}  # evening 5: the act arm's extra forge args (modes first; "all" = every kind)
OUT=data/runs/build3-surface-read-$NAME
mkdir -p "$OUT"
SRC_JAR=${JAR:-$(ls -t $FORGE/forge-gui-desktop/target/*jar-with-dependencies.jar | head -1)}
JAR="$OUT/forge-$NAME.jar"
if [[ ! -f "$JAR" ]]; then
  cp "$SRC_JAR" "$JAR"; git -C "$FORGE" rev-parse HEAD > "$OUT/forge-$NAME.commit"; sha256sum "$JAR" > "$OUT/forge-$NAME.sha256"
fi
export PYTHONUNBUFFERED=1 DISPLAY=:0
export XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1)
LOG="$OUT/chain.log"
log() { echo "$(date -Iseconds) $*" | tee -a "$LOG"; }
# ADR-0107: launched through `python -m anvil.runs launch --name build3-read-$NAME --dir $OUT -- bash scripts/build3_surface_read.sh`;
# the supervisor records done / failed (with the log tail), ticks the stall check and queues the alert — nothing here notifies.
finish() { exit $1; }
arms_of() { ls -dt data/runs/${1}arm-s0-* | head -1 | tr -d '\n'; echo -n ","; ls -dt data/runs/${1}arm-s1-* | head -1; }
run_arm() { # tag [server-tags] [forge-args] [server-args override]
  local tag=$1 stags=${2:-} fargs="${FORGE_ARGS:+$FORGE_ARGS }${3:-}" sargs="${4:-$SERVER_ARGS}"
  if [[ -f "$OUT/$tag.done" ]]; then log "arm $tag done already"; return 0; fi
  local extra=()
  if [[ -n "$stags" ]]; then extra=(--server-tags "$stags"); fi
  if [[ -n "${fargs// /}" ]]; then extra+=("--forge-args=$fargs"); fi  # the = form: a value starting with '-' (e.g. -payrescue) is otherwise read as a flag
  if [[ -n "$sargs" ]]; then extra+=(--server-args "$sargs"); fi
  if [[ "$fargs" == *-search* ]]; then extra+=(--labels); fi  # the harness refuses -search without -labels (the 09-15 b3e5 launch failed on it)
  nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT" --name "$NAME-$tag" --games "$GAMES" \
      --workers "$WORKERS" --port "$PORT" --servers "$SERVERS" --jar "$JAR" --skip-ante "${extra[@]}" >> "$OUT/$tag.log" 2>&1 || return 1
  arms_of "$NAME-$tag" > "$OUT/$tag.done"
  log "arm $tag done: $(cat $OUT/$tag.done)"
}
log "start ckpt=$CKPT jar=$SRC_JAR ($(cat $OUT/forge-$NAME.commit)) games=$GAMES/seat"
ARMSPEC=()
for arm in $ARMS; do
  case $arm in
    off) run_arm off "$TAGS_OFF" || { log "arm off FAILED"; finish 1; } ;;
    on) run_arm on || { log "arm on FAILED"; finish 1; } ;;
    rescue) run_arm rescue "" "$FORGE_ARGS_RESCUE" || { log "arm rescue FAILED"; finish 1; } ;;
    autoonly) run_arm autoonly "" "" "--pay-bar 100" || { log "arm autoonly FAILED"; finish 1; } ;;  # the tag bridged, auto on every window (the probe-path arm)
    act) run_arm act "" "$FORGE_ARGS_ACT" || { log "arm act FAILED"; finish 1; } ;;  # evening 5 (ADR-0106 A6): the on arm + surface acting (FORGE_ARGS carries the search recipe on every arm)
    *) log "unknown arm $arm"; finish 1 ;;
  esac
  ARMSPEC+=(--arm "$arm=$(cat $OUT/$arm.done)")
done
uv run python scripts/build2_read.py arms "${ARMSPEC[@]}" --out "$OUT/read.json" >> "$OUT/read.log" 2>&1 || { log "read FAILED"; finish 1; }
log "read: $(python3 -c "import json; r=json.load(open('$OUT/read.json')); print(json.dumps(r.get('paired', r))[:600])")"
finish 0
