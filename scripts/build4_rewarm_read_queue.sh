#!/usr/bin/env bash
# Build 4: the re-warm's strength read, queued behind the re-warm (data/training/m12-build4-rw/last.pt):
# the served build m12-build4-e1 (arm "on": every tag) vs the re-warmed m12-build4-rw (arm "alt"),
# 300 games per seat, network alone, one jar, the mode gate off on both (the retired gate).
# Launched through anvil.runs (its dir = OUT).
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=${OUT:-$REPO/data/runs/build4-rewarm-read}; mkdir -p "$OUT"
RW=${RW:-data/training/m12-build4-rw/last.pt}
NAME=${NAME:-b4rw}  # the read's name (a fresh one per re-warm: the read script skips arms whose .done exists)
RW_RUN=${RW_RUN:-build4-rewarm}
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "waiting for $RW"
until [ -f "$RW" ]; do sleep 60; touch "$OUT/.waiting"; done
st=$(python3 -c "import json; print(json.load(open('/home/tyrathalis/.local/state/anvil/runs/$RW_RUN.json'))['state'])" 2>/dev/null)
log "re-warm state: $st; launching the paired read"
NAME="$NAME" CKPT=data/training/m12-build4-e1/last.pt CKPT_ALT="$RW" GAMES=300 WORKERS=24 SERVERS=2 PORT=50069 ARMS="on alt" \
  FORGE_ARGS="-modegate off" JAR="$REPO/data/runs/build4-targets/forge-targets-gate.jar" \
  uv run python -m anvil.runs launch --name "build4-read-$NAME" --dir "$REPO/data/runs/build3-surface-read-$NAME" --stall-min 60 -- bash scripts/build3_surface_read.sh
uv run python -m anvil.runs wait --name "build4-read-$NAME"; rc=$?
log "paired read rc=$rc: $(tail -1 data/runs/build3-surface-read-$NAME/chain.log | cut -c1-400)"
echo OK > "$OUT/DONE"
