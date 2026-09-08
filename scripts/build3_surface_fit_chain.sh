#!/usr/bin/env bash
# M12 Build 3 (ADR-0105): the surface imitation fit chain for one evening —
# the remaining cross-fit folds, the pooled read, then the build on every
# game -> the checkpoint the server serves (surface_fit.py). Resumable: a fold
# whose result-foldK.json exists is skipped. Detached-run checklist: setsid
# nohup by the caller; watchd + notify inside.
# Usage: build3_surface_fit_chain.sh
#   env: OUT (data/runs/build3-e1), CKPT_OUT (data/training/m12-build3-e1),
#        TASKS (surf_one,surf_set), FOLDS (5), STEPS (4000), EPOCHS (2), WORKERS (4),
#        STORES (surface_fit's default glob), DISTILL (a -searchsurf run dir with
#        sub-row frames — evening 2; empty = imitation only), DISTILL_W (1.0),
#        DISTILL_T (0.025), DISTILL_KINDS (entity_one,entity_set,mode)
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
cd "$REPO"
OUT=${OUT:-data/runs/build3-e1}
CKPT_OUT=${CKPT_OUT:-data/training/m12-build3-e1}
TASKS=${TASKS:-surf_one,surf_set}
FOLDS=${FOLDS:-5}; STEPS=${STEPS:-4000}; EPOCHS=${EPOCHS:-2}; WORKERS=${WORKERS:-4}
STORES=${STORES:-}; DISTILL=${DISTILL:-}; DISTILL_W=${DISTILL_W:-1.0}; DISTILL_T=${DISTILL_T:-0.025}
DISTILL_KINDS=${DISTILL_KINDS:-entity_one,entity_set,mode}
EXTRA=()
[[ -n "$STORES" ]] && EXTRA+=(--stores "$STORES")
[[ -n "$DISTILL" ]] && EXTRA+=(--distill "$DISTILL" --distill-weight "$DISTILL_W" --distill-temp "$DISTILL_T" --distill-kinds "$DISTILL_KINDS")
export PYTHONUNBUFFERED=1
mkdir -p "$OUT"
LOG="$OUT/chain.log"
log() { echo "$(date -Iseconds) $*" | tee -a "$LOG"; }
python3 scripts/anvil_watchd.py register --name build3-fit --pid $$ --dir "$REPO/$OUT" --stall-min 45
notify() { python3 -c "from anvil.training.notify import notify; notify('$1', '$2', tag='build3')"; }
finish() { python3 scripts/anvil_watchd.py unregister --name build3-fit; if [[ $1 -eq 0 ]]; then notify "anvil build3 surface fit chain DONE" "$OUT"; else notify "anvil build3 surface fit chain FAILED" "rc=$1 see $LOG"; fi; exit $1; }
log "chain start out=$OUT tasks=$TASKS folds=$FOLDS steps=$STEPS stores=${STORES:-default} distill=${DISTILL:-none} w=$DISTILL_W T=$DISTILL_T"
for f in $(seq 0 $((FOLDS-1))); do
  if [[ -f "$OUT/result-fold$f.json" ]]; then log "fold $f done already"; continue; fi
  log "fold $f start"
  nice -n 10 uv run python -m anvil.training.surface_fit --out "$OUT" --fold "$f" --folds "$FOLDS" --tasks "$TASKS" \
      --steps "$STEPS" --epochs "$EPOCHS" --workers "$WORKERS" --batch 64 "${EXTRA[@]}" >> "$OUT/fold$f.log" 2>&1 || { log "fold $f FAILED"; finish 1; }
  log "fold $f done: $(python3 -c "import json; r=json.load(open('$OUT/result-fold$f.json')); print({k: v['exact_agree'] for k, v in r['held_out'].items() if '/' not in k})")"
done
nice -n 10 uv run python -m anvil.training.surface_fit --out "$OUT" --read --folds "$FOLDS" --tasks "$TASKS" ${STORES:+--stores "$STORES"} >> "$OUT/read.log" 2>&1 || { log "read FAILED"; finish 1; }
log "read: $(head -12 $OUT/read.md | tail -8 | tr '\n' ' ')"
if [[ ! -f "$CKPT_OUT/last.pt" ]]; then
  log "build start"
  nice -n 10 uv run python -m anvil.training.surface_fit --out "$OUT" --build --ckpt-out "$CKPT_OUT" --folds "$FOLDS" --tasks "$TASKS" \
      --steps "$STEPS" --epochs "$EPOCHS" --workers "$WORKERS" --batch 64 "${EXTRA[@]}" >> "$OUT/build.log" 2>&1 || { log "build FAILED"; finish 1; }
fi
log "build done: $CKPT_OUT/last.pt"
finish 0
