#!/usr/bin/env bash
# Build 4 (09-17 01:05): after the anchored re-warm's -18.8 pp — (1) the priority-only read of rw2 vs e1
# (every other head the heuristic's: isolates the re-warmed priority policy from the heads that read the
# moved trunk), then (2) the frozen-trunk re-warm (--unfreeze 0: the new paths + the pointer / value heads
# only) -> m12-build4-rw3, then (3) rw3's full read and priority-only read. Launched through anvil.runs.
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=${OUT:-$REPO/data/runs/build4-rewarm3}; mkdir -p "$OUT"
JAR=$REPO/data/runs/build4-targets/forge-targets-gate.jar
E1=data/training/m12-build4-e1/last.pt; RW2=data/training/m12-build4-rw2/last.pt; RW3=data/training/m12-build4-rw3/last.pt
PRIO_TAGS="mtg.priority,mtg.mulligan_keep"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
read_pair() { # name ckpt_alt arms tags_off
  NAME="$1" CKPT="$E1" CKPT_ALT="$2" GAMES=300 WORKERS=24 SERVERS=2 PORT=50069 ARMS="$3" TAGS_OFF="$4" FORGE_ARGS="-modegate off" JAR="$JAR" \
    uv run python -m anvil.runs launch --name "build4-read-$1" --dir "$REPO/data/runs/build3-surface-read-$1" --stall-min 60 -- bash scripts/build3_surface_read.sh
  uv run python -m anvil.runs wait --name "build4-read-$1"; log "read $1 rc=$?: $(tail -1 data/runs/build3-surface-read-$1/chain.log | cut -c1-300)"
}
log "1. the priority-only read: e1 vs rw2 (tags $PRIO_TAGS)"
read_pair b4rw2p "$RW2" "off altoff" "$PRIO_TAGS"
log "2. the frozen-trunk re-warm -> $RW3"
if [ ! -f "$RW3" ]; then
  uv run python -m anvil.runs launch --name build4-rewarm3 --dir "$REPO/data/runs/build4-rewarm3-fit" --stall-min 60 -- uv run python -m anvil.training.search_distill \
    --runs 'data/runs/b2-dzla05arm-s*-2026*,data/runs/b2-dzla10arm-s*-2026*,data/runs/b3-surflab*-2026*,data/runs/b4-tgtlab-2026*' \
    --init "$E1" --out data/runs/build4-rewarm3-fit --ckpt-out data/training/m12-build4-rw3 --steps 8000 --workers 6 --w-value 0.25 --w-anchor 1.0 --unfreeze 0 --eval-every 1000 --eval-batches 150
  uv run python -m anvil.runs wait --name build4-rewarm3; log "re-warm 3 rc=$?"
fi
[ -f "$RW3" ] || { log "no rw3 ckpt — stopping"; exit 1; }
log "3. rw3's reads: full (on vs alt) and priority-only (off vs altoff)"
read_pair b4rw3 "$RW3" "on alt" "mtg.priority,mtg.mulligan_keep,mtg.mulligan_tuck,mtg.trigger,mtg.binary,mtg.number,mtg.attack,mtg.block,mtg.surface.entity_one,mtg.surface.entity_set,mtg.surface.mode,mtg.surface.order,mtg.surface.damage"
read_pair b4rw3p "$RW3" "off altoff" "$PRIO_TAGS"
echo OK > "$OUT/DONE"
