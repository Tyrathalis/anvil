#!/usr/bin/env bash
# THE HELD-OUT PRECON READ (M13 Build 0 step 5; m13-plan.md, ADR-0130): the checkpoint of record, network
# alone, against the plain heuristic on Commander precon decks, two-player. No arm trains anything.
# Three arms on the same seeds and deck pairs:
#   asis      the checkpoint as it is: a card outside its pool is served as "no card", the old ability table
#   idnull    the card table extended with the new cards' text and features (scripts/m13_precon_table.py),
#             each new card on the no-card id row; the ability table extended with the precon keys
#   idmean    the same, each new card on the mean of the trained id rows
# The decks are Forge's own precon files, copied to ~/.forge/decks/commander/anvil-precons/ as pc-NNN.dck
# (data/runs/m13-precon/deck-map.json names them and holds each deck's share of unseen cards).
# Idempotent on relaunch (the .done markers).
# Launch:
#   uv run python -m anvil.runs launch --name m13-precon --dir data/runs/m13-precon/read \
#     --launched-by '<ListAgents name> [<ref>]' --watch 'data/runs/pc-*' --stall-min 120 -- bash scripts/m13_precon.sh
#   env: CKPT, VERSION (the extended table's version), JAR, PAIRS, SEED_BASE, GAMES (per seat), WORKERS, ARMS
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
P=$REPO/data/runs/m13-precon
CKPT=${CKPT:-data/training/big-run/iter-405/train/last.pt}
VERSION=${VERSION:?the extended card table version, e.g. precon-1a2b3c4d}
JAR=${JAR:-$REPO/data/runs/m13-mc/forge-m13-mc-switch.jar}
PAIRS=${PAIRS:-$P/pairs.txt}
SEED_BASE=${SEED_BASE:-20261121}; GAMES=${GAMES:-2500}; WORKERS=${WORKERS:-24}; ARMS=${ARMS:-"asis idnull idmean"}
OUT=${OUT_DIR:-$P/read}; mkdir -p "$OUT"
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
arm() { # <tag> <ckpt> <ability table stem>
  local tag=$1 ckpt=$2 abil=$3
  [[ -f "$OUT/$tag.done" ]] && return 0
  log "arm $tag: ckpt=$ckpt abilities=$abil games=$GAMES/seat seeds=$SEED_BASE"
  nice -n 19 uv run python scripts/final_read.py --ckpt "$ckpt" --name "pc-$tag" --games "$GAMES" --games-per-pair 5 \
    --seed-base "$SEED_BASE" --workers "$WORKERS" --port 50086 --servers 0 --jar "$JAR" --skip-ante \
    --pairs-file "$PAIRS" --pool-version "$VERSION" --server-args "--abilities $abil" >> "$OUT/$tag.log" 2>&1 \
    || { log "arm $tag FAILED"; return 1; }
  echo "$(ls -dt "data/runs/pc-${tag}arm-s0-"* | head -1),$(ls -dt "data/runs/pc-${tag}arm-s1-"* | head -1)" > "$OUT/$tag.done"
}
log "precon read: ckpt=$CKPT table=$VERSION jar=$JAR pairs=$PAIRS arms='$ARMS'"
for t in $ARMS; do
  case "$t" in
    asis)   arm asis "$CKPT" data/embeddings/abil-cf2ca6ba-m13-qwen3 || exit 1 ;;
    idnull) arm idnull "$P/ckpt-$VERSION-idnull.pt" data/embeddings/abil-precon-m13-qwen3 || exit 1 ;;
    idmean) arm idmean "$P/ckpt-$VERSION-idmean.pt" data/embeddings/abil-precon-m13-qwen3 || exit 1 ;;
    *) log "unknown arm $t"; exit 2 ;;
  esac
done
uv run python scripts/m13_precon_report.py --out "$OUT" --map "$P/deck-map.json" > "$OUT/read.md" 2> "$OUT/report.err" \
  || { log "report FAILED: $(tail -2 "$OUT/report.err")"; exit 1; }
cat "$OUT/read.md" | tee -a "$OUT/queue.log"
log "precon read done"; echo OK > "$OUT/DONE"
