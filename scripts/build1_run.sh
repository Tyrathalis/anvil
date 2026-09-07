#!/usr/bin/env bash
# M12 Build 1 driver (ADR-0103): five cross-fit folds -> the day-zero build
# -> the read. Resumable: a fold with its result file is skipped.
# Usage: build1_run.sh [out=data/runs/m12-build1] [extra fit args...]
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
OUT=${1:-data/runs/m12-build1}; shift || true
CKPT_OUT=${CKPT_OUT:-data/training/m12-build1}
export PYTHONUNBUFFERED=1
cd "$REPO"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/driver.log"; }
for k in 0 1 2 3 4; do
  if [[ -f "$OUT/result-fold$k.json" ]]; then log "fold $k done, skipping"; continue; fi
  log "fold $k start"
  nice -n 19 uv run python -m anvil.training.value_pretrain fit --out "$OUT" --fold $k "$@" \
    > "$OUT/fit-fold$k.log" 2>&1 || { log "fold $k FAILED rc=$?"; exit 1; }
  log "fold $k done: $(python3 -c "import json;r=json.load(open('$OUT/result-fold$k.json'));print(r['state_holdout_spearman'], r['oneply_test']['eot/k1'])")"
done
if [[ ! -f "$OUT/result-build.json" ]]; then
  log "build start"
  nice -n 19 uv run python -m anvil.training.value_pretrain fit --out "$OUT" --build --ckpt-out "$CKPT_OUT" "$@" \
    > "$OUT/fit-build.log" 2>&1 || { log "build FAILED rc=$?"; exit 1; }
fi
uv run python -m anvil.training.value_pretrain read --out "$OUT" | tee -a "$OUT/driver.log"
uv run python -c "
from anvil.training.notify import notify
import json; r=json.load(open('$OUT/build1-read.json'))
notify('M12 Build 1 read', f\"{r['verdict']}: one-ply {r['oneply_crossfit'].get('eot/k1',{}).get('spearman_mean')} state {r['state_holdout_spearman']}\")
" 2>/dev/null || true
log "ALL DONE"
