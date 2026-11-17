#!/usr/bin/env bash
# The ladder of own checkpoints (ADR-0126 decision 3; docs/design/m13-prescoping-measurements.md, section 1):
# nine head-to-head reads among five checkpoints, network-alone, masked, on one seed base. The four adjacent
# pairs play ADJ_GAMES per seat assignment and the five longer pairs FAR_GAMES. The tenth pair
# (iter-405 against the warm start) is already on file from another seed base and is not replayed.
# Idempotent on relaunch: a pair whose report file exists is skipped.
# Launch:
#   uv run python -m anvil.runs launch --name ladder --dir data/runs/ladder \
#     --launched-by '<ListAgents name> [<ref>]' --watch 'data/runs/lad-*' --stall-min 120 -- bash scripts/ladder_chain.sh
#   env: SEED_BASE, ADJ_GAMES (2500 / seat), FAR_GAMES (1000 / seat), JAR, WORKERS (24)
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
JAR=${JAR:-$REPO/data/runs/tgtmask/forge-tgtmask3.jar}
SEED_BASE=${SEED_BASE:-20261116}; ADJ_GAMES=${ADJ_GAMES:-2500}; FAR_GAMES=${FAR_GAMES:-1000}; WORKERS=${WORKERS:-24}
OUT=$REPO/data/runs/ladder; mkdir -p "$OUT"
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
ckpt() {
  case "$1" in
    start) echo data/training/shakedown-alloc/iter-019/train/last.pt ;;
    *)     echo "data/training/big-run/iter-$1/train/last.pt" ;;
  esac
}
# A is the later checkpoint, so every reported score is the later one's.
PAIRS="099:start:$ADJ_GAMES 301:099:$ADJ_GAMES 405:301:$ADJ_GAMES 513:405:$ADJ_GAMES
       301:start:$FAR_GAMES 513:start:$FAR_GAMES 405:099:$FAR_GAMES 513:099:$FAR_GAMES 513:301:$FAR_GAMES"
for p in $PAIRS; do
  IFS=: read -r a b games <<< "$p"
  name="lad-$a-$b"; A=$(ckpt "$a"); B=$(ckpt "$b")
  [[ -f "$A" && -f "$B" ]] || { log "$name: a checkpoint is missing ($A, $B)"; exit 1; }
  if [[ -f "$REPO/data/runs/$name-h2h.json" ]]; then log "$name: report on file, skipped"; continue; fi
  log "$name: A=$A B=$B games=$games/seat seed_base=$SEED_BASE"
  uv run python scripts/h2h_read.py --a "$A" --b "$B" --name "$name" --games "$games" \
    --seed-base "$SEED_BASE" --workers "$WORKERS" --port 50086 --jar "$JAR" >> "$OUT/$name.log" 2>&1 \
    || { log "$name FAILED"; exit 1; }
  log "$name done: $(grep -o 'A score.*' "$OUT/$name.log" | tail -1)"
done
echo OK > "$OUT/DONE"
log "ladder done"
