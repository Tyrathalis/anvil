#!/usr/bin/env bash
# M12 Build 3 (ADR-0105): the surface imitation fit chain for one evening —
# the remaining cross-fit folds, the pooled read, then the build on every
# game -> the checkpoint the server serves (surface_fit.py). Resumable: a fold
# whose result-foldK.json exists is skipped. Detached-run checklist: setsid
# nohup by the caller; watchd + notify inside.
# Usage: build3_surface_fit_chain.sh
#   env: OUT (data/runs/build3-e1), CKPT_OUT (data/training/m12-build3-e1),
#        TASKS (surf_one,surf_set), FOLDS (5), STEPS (4000), EPOCHS (2), WORKERS (4)
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
cd "$REPO"
OUT=${OUT:-data/runs/build3-e1}
CKPT_OUT=${CKPT_OUT:-data/training/m12-build3-e1}
TASKS=${TASKS:-surf_one,surf_set}
FOLDS=${FOLDS:-5}; STEPS=${STEPS:-4000}; EPOCHS=${EPOCHS:-2}; WORKERS=${WORKERS:-4}
export PYTHONUNBUFFERED=1
mkdir -p "$OUT"
LOG="$OUT/chain.log"
log() { echo "$(date -Iseconds) $*" | tee -a "$LOG"; }
python3 scripts/anvil_watchd.py register --name build3-fit --pid $$ --dir "$REPO/$OUT" --stall-min 45
notify() { python3 -c "from anvil.training.notify import notify; notify('$1', '$2', tag='build3')"; }
finish() { python3 scripts/anvil_watchd.py unregister --name build3-fit; if [[ $1 -eq 0 ]]; then notify "anvil build3 surface fit chain DONE" "$OUT"; else notify "anvil build3 surface fit chain FAILED" "rc=$1 see $LOG"; fi; exit $1; }
log "chain start out=$OUT tasks=$TASKS folds=$FOLDS steps=$STEPS"
for f in $(seq 0 $((FOLDS-1))); do
  if [[ -f "$OUT/result-fold$f.json" ]]; then log "fold $f done already"; continue; fi
  log "fold $f start"
  nice -n 10 uv run python -m anvil.training.surface_fit --out "$OUT" --fold "$f" --folds "$FOLDS" --tasks "$TASKS" \
      --steps "$STEPS" --epochs "$EPOCHS" --workers "$WORKERS" --batch 64 >> "$OUT/fold$f.log" 2>&1 || { log "fold $f FAILED"; finish 1; }
  log "fold $f done: $(python3 -c "import json; r=json.load(open('$OUT/result-fold$f.json')); print({k: v['exact_agree'] for k, v in r['held_out'].items() if '/' not in k})")"
done
nice -n 10 uv run python -m anvil.training.surface_fit --out "$OUT" --read --folds "$FOLDS" --tasks "$TASKS" >> "$OUT/read.log" 2>&1 || { log "read FAILED"; finish 1; }
log "read: $(head -12 $OUT/read.md | tail -8 | tr '\n' ' ')"
if [[ ! -f "$CKPT_OUT/last.pt" ]]; then
  log "build start"
  nice -n 10 uv run python -m anvil.training.surface_fit --out "$OUT" --build --ckpt-out "$CKPT_OUT" --folds "$FOLDS" --tasks "$TASKS" \
      --steps "$STEPS" --epochs "$EPOCHS" --workers "$WORKERS" --batch 64 >> "$OUT/build.log" 2>&1 || { log "build FAILED"; finish 1; }
fi
log "build done: $CKPT_OUT/last.pt"
finish 0
