#!/usr/bin/env bash
# Build 4 (ADR-0109): the targets evening's chain — waits for the target label pool
# (build3_surface_labels.sh's DONE), ingests it, folds its side-table keys into the ability
# table (b4s: the b4 rows byte-identical), cross-fits the surface decoder on the six tasks +
# surf_target (build3_surface_fit_chain.sh: 5 folds -> read -> build -> the b4e1 ckpt), smokes
# the served heads on the read jar, then runs the three-arm paired read (build3_surface_read.sh:
# off = the new ckpt with the target tag withheld = today's served set, on = + targets (gated
# mode), nogate = + targets with -modegate off). Pre-registered (ADR-0109): nogate within one SE
# of on -> the playability gate retires; a clear negative -> the gate stays, attributed on the
# ladder. Resumable at every stage (a stage whose artifact exists is skipped).
# Launched through anvil.runs (its dir = OUT).
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
POOL_OUT=${POOL_OUT:-data/runs/build4-target-labels}
OUT=${OUT:-data/runs/build4-e1}
CKPT_OUT=${CKPT_OUT:-data/training/m12-build4-e1}
JAR=${JAR:-$REPO/data/runs/build4-targets/forge-targets-gate.jar}
BASE_ABIL=${BASE_ABIL:-data/embeddings/abil-cf2ca6ba-b4-qwen3}
ABIL_OUT=${ABIL_OUT:-abil-cf2ca6ba-b4s-qwen3}
TASKS=${TASKS:-surf_one,surf_set,surf_mode,surf_order,surf_damage,surf_target}
READ_NAME=${READ_NAME:-b4e1}; READ_GAMES=${READ_GAMES:-300}; ARMS=${ARMS:-off on nogate}
TAGS_OFF=${TAGS_OFF:-mtg.priority,mtg.mulligan_keep,mtg.mulligan_tuck,mtg.trigger,mtg.binary,mtg.number,mtg.attack,mtg.block,mtg.surface.entity_one,mtg.surface.entity_set,mtg.surface.mode,mtg.surface.order,mtg.surface.damage}
mkdir -p "$OUT"; LOG="$OUT/chain.log"
log() { echo "$(date -Iseconds) $*" | tee -a "$LOG"; }
state() { echo "{\"stage\":\"$1\",\"at\":\"$(date -Iseconds)\"}" >> "$OUT/stages.jsonl"; }
export PYTHONUNBUFFERED=1

# ---- 1. the pool
log "waiting for $POOL_OUT/DONE"
while [[ ! -f "$POOL_OUT/DONE" ]]; do sleep 120; touch "$OUT/.waiting"; done
RUN=$(python3 -c "import json; print(json.load(open('$POOL_OUT/DONE'))['run'])")
RC=$(python3 -c "import json; print(json.load(open('$POOL_OUT/DONE'))['rc'])")
log "pool landed: $RUN rc=$RC"
[[ "$RC" == "0" ]] || { log "pool rc=$RC — stopping"; exit 1; }
STORE="data/trajectories/$(basename $RUN)"
if [[ ! -d "$STORE" ]]; then
  state ingest; uv run python -m anvil.store ingest "$RUN" > "$OUT/ingest.log" 2>&1 || { log "ingest FAILED"; exit 1; }
  log "ingested -> $STORE"
fi
if [[ ! -f "$OUT/pool-read.md" ]]; then
  uv run python scripts/build3_label_read.py --run "$RUN" --abilities "$BASE_ABIL" > "$OUT/pool-read.md" 2>&1
  log "pool read -> $OUT/pool-read.md: $(sed -n 3p $OUT/pool-read.md | cut -c1-160)"
fi
# ---- 2. the ability table with the pool's side-table keys folded in (b4 rows byte-identical)
if [[ ! -f "data/embeddings/$ABIL_OUT.safetensors" ]]; then
  state abil
  uv run python scripts/extend_ability_table.py --base "$BASE_ABIL" --stores "$STORE" --out "$ABIL_OUT" > "$OUT/abil.log" 2>&1 || { log "table extension FAILED"; exit 1; }
  log "table -> data/embeddings/$ABIL_OUT: $(grep '^\[extend\]' $OUT/abil.log | tail -1)"
fi
# ---- 3. the fit chain (5 folds -> read -> build)
if [[ ! -f "$CKPT_OUT/last.pt" ]]; then
  state fit
  OUT="$OUT" CKPT_OUT="$CKPT_OUT" TASKS="$TASKS" FOLDS=5 STEPS=4000 WORKERS=4 \
    STORES="data/trajectories/b2-*,data/trajectories/b3-surflab2-*,$STORE" DISTILL="$RUN" \
    DISTILL_KINDS=entity_one,entity_set,mode,target ABIL="data/embeddings/$ABIL_OUT" \
    bash scripts/build3_surface_fit_chain.sh || { log "fit chain FAILED"; exit 1; }
  log "fit chain done -> $CKPT_OUT/last.pt"
fi
# ---- 4. the served-head smoke on the read jar
if [[ ! -f "$OUT/smoke/DONE" ]]; then
  state smoke
  OUT="$OUT/smoke" CKPT="$REPO/$CKPT_OUT/last.pt" JAR="$JAR" PORT=50079 bash scripts/build3_surface_smoke.sh 8 0.2 2 8 > "$OUT/smoke.log" 2>&1 || { log "smoke FAILED (see $OUT/smoke.log)"; exit 1; }
  grep -q "anvil rc=0" "$OUT/smoke.log" || { log "smoke FAILED: the harness did not exit 0 (see $OUT/smoke.log)"; exit 1; }
  log "smoke done: $(tail -1 $OUT/smoke.log | cut -c1-200)"
fi
# ---- 5. the three-arm paired read
state read
NAME="$READ_NAME" CKPT="$CKPT_OUT/last.pt" GAMES="$READ_GAMES" WORKERS=24 SERVERS=2 PORT=50067 ARMS="$ARMS" TAGS_OFF="$TAGS_OFF" JAR="$JAR" \
  uv run python -m anvil.runs launch --name "build4-read-$READ_NAME" --dir "data/runs/build3-surface-read-$READ_NAME" --stall-min 60 -- bash scripts/build3_surface_read.sh
uv run python -m anvil.runs wait --name "build4-read-$READ_NAME"; rc=$?
log "paired read rc=$rc: $(tail -1 data/runs/build3-surface-read-$READ_NAME/chain.log | cut -c1-400)"
echo OK > "$OUT/DONE"; state done
