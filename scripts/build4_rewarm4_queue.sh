#!/usr/bin/env bash
# Build 4 (09-17 02:15): the re-warm on the FIXED join (every searched row aligned to its dec; the first
# two re-warms trained on the 12.5% mana-free slice): (1) rw4 = the anchored recipe (unfreeze 2) ->
# its full read (on vs alt) + priority-only read (off vs altoff); (2) rw5 = the same with the trunk
# frozen (unfreeze 0) -> its full read. Launched through anvil.runs.
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=${OUT:-$REPO/data/runs/build4-rewarm4}; mkdir -p "$OUT"
JAR=$REPO/data/runs/build4-targets/forge-targets-gate.jar
E1=data/training/m12-build4-e1/last.pt
RUNS='data/runs/b2-dzla05arm-s*-2026*,data/runs/b2-dzla10arm-s*-2026*,data/runs/b3-surflab*-2026*,data/runs/b4-tgtlab-2026*'
PRIO_TAGS="mtg.priority,mtg.mulligan_keep"
ALL_TAGS="mtg.priority,mtg.mulligan_keep,mtg.mulligan_tuck,mtg.trigger,mtg.binary,mtg.number,mtg.attack,mtg.block,mtg.surface.entity_one,mtg.surface.entity_set,mtg.surface.mode,mtg.surface.order,mtg.surface.damage"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
fit() { # name unfreeze
  local ck=data/training/m12-build4-$1/last.pt
  [ -f "$ck" ] && { log "fit $1 exists"; return 0; }
  uv run python -m anvil.runs launch --name "build4-rewarm-$1" --dir "$REPO/data/runs/build4-rewarm-$1" --stall-min 60 -- uv run python -m anvil.training.search_distill \
    --runs "$RUNS" --init "$E1" --out "data/runs/build4-rewarm-$1" --ckpt-out "data/training/m12-build4-$1" --steps 8000 --workers 6 --w-value 0.25 --w-anchor 1.0 --unfreeze "$2" --eval-every 1000 --eval-batches 150
  uv run python -m anvil.runs wait --name "build4-rewarm-$1"; log "fit $1 rc=$?"
  [ -f "$ck" ] || { log "no $1 ckpt — stopping"; exit 1; }
}
read_pair() { # name ckpt_alt arms tags_off
  NAME="$1" CKPT="$E1" CKPT_ALT="$2" GAMES=300 WORKERS=24 SERVERS=2 PORT=50069 ARMS="$3" TAGS_OFF="$4" FORGE_ARGS="-modegate off" JAR="$JAR" \
    uv run python -m anvil.runs launch --name "build4-read-$1" --dir "$REPO/data/runs/build3-surface-read-$1" --stall-min 60 -- bash scripts/build3_surface_read.sh
  uv run python -m anvil.runs wait --name "build4-read-$1"; log "read $1 rc=$?: $(tail -1 data/runs/build3-surface-read-$1/chain.log | cut -c1-300)"
}
fit rw4 2
read_pair b4rw4 data/training/m12-build4-rw4/last.pt "on alt" "$ALL_TAGS"
read_pair b4rw4p data/training/m12-build4-rw4/last.pt "off altoff" "$PRIO_TAGS"
fit rw5 0
read_pair b4rw5 data/training/m12-build4-rw5/last.pt "on alt" "$ALL_TAGS"
echo OK > "$OUT/DONE"
