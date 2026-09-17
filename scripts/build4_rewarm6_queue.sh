#!/usr/bin/env bash
# Build 4 (09-17 05:20): the re-warm with the void options as playability negatives — rw6 = rw4's
# recipe + the void term (w_kl 1, T 0.025, unfreeze 2); rw7 = the same, softer (w_kl 0.3, T 0.05);
# each -> its full read (on vs alt). Launched through anvil.runs.
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=${OUT:-$REPO/data/runs/build4-rewarm6}; mkdir -p "$OUT"
JAR=$REPO/data/runs/build4-targets/forge-targets-gate.jar
E1=data/training/m12-build4-e1/last.pt
RUNS='data/runs/b2-dzla05arm-s*-2026*,data/runs/b2-dzla10arm-s*-2026*,data/runs/b3-surflab*-2026*,data/runs/b4-tgtlab-2026*'
ALL_TAGS="mtg.priority,mtg.mulligan_keep,mtg.mulligan_tuck,mtg.trigger,mtg.binary,mtg.number,mtg.attack,mtg.block,mtg.surface.entity_one,mtg.surface.entity_set,mtg.surface.mode,mtg.surface.order,mtg.surface.damage"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
fit() { # name extra-args...
  local name=$1; shift
  local ck=data/training/m12-build4-$name/last.pt
  [ -f "$ck" ] && { log "fit $name exists"; return 0; }
  uv run python -m anvil.runs launch --name "build4-rewarm-$name" --dir "$REPO/data/runs/build4-rewarm-$name" --stall-min 60 -- uv run python -m anvil.training.search_distill \
    --runs "$RUNS" --init "$E1" --out "data/runs/build4-rewarm-$name" --ckpt-out "data/training/m12-build4-$name" --steps 8000 --workers 6 --w-value 0.25 --w-anchor 1.0 --w-void 1.0 --unfreeze 2 --eval-every 1000 --eval-batches 150 "$@"
  uv run python -m anvil.runs wait --name "build4-rewarm-$name"; log "fit $name rc=$?"
  [ -f "$ck" ] || { log "no $name ckpt — stopping"; exit 1; }
}
read_pair() { # name ckpt_alt
  NAME="$1" CKPT="$E1" CKPT_ALT="$2" GAMES=300 WORKERS=24 SERVERS=2 PORT=50069 ARMS="on alt" TAGS_OFF="$ALL_TAGS" FORGE_ARGS="-modegate off" JAR="$JAR" \
    uv run python -m anvil.runs launch --name "build4-read-$1" --dir "$REPO/data/runs/build3-surface-read-$1" --stall-min 60 -- bash scripts/build3_surface_read.sh
  uv run python -m anvil.runs wait --name "build4-read-$1"; log "read $1 rc=$?: $(tail -1 data/runs/build3-surface-read-$1/chain.log | cut -c1-300)"
}
fit rw6
read_pair b4rw6 data/training/m12-build4-rw6/last.pt
fit rw7 --w-kl 0.3 --temp 0.05
read_pair b4rw7 data/training/m12-build4-rw7/last.pt
echo OK > "$OUT/DONE"
