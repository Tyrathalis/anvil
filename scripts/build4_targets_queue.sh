#!/usr/bin/env bash
# Build 4 (ADR-0109): the target surface's proof + smoke, in order on one jar snapshot (JAR):
#   1. the recipe smoke (4 games, 2 workers; the e3 build serving its six surfaces on the
#      extended ability table, -searchsurf 2 / rolls 2 / acting at 0.10): TARGET windows
#      recorded, forced on copies, no crash class — build3_label_read.py over the run
#   2. the forkcheck on the targets tip (flag-off identity vs the merge baseline; the pin's
#      proof) — run_forkcheck.sh detaches its java, so this script waits on results.jsonl
# Launched through anvil.runs (its dir = OUT).
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=${OUT:-$REPO/data/runs/build4-targets}; mkdir -p "$OUT"
JAR=${JAR:-$OUT/forge-targets.jar}
FC=${FC:-$REPO/data/forkcheck/run-20260916-build4-targets}
ABIL=${ABIL:-data/embeddings/abil-cf2ca6ba-b4-qwen3}
CKPT=${CKPT:-data/training/m12-build3-e3/last.pt}
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
git -C ../forge rev-parse HEAD > "$OUT/forge-targets.commit"
log "smoke start jar=$JAR ($(cat $OUT/forge-targets.commit))"
WT=$REPO NAME=b4-tgt-smoke OUT=$OUT/smoke GAMES=${SMOKE_GAMES:-4} WORKERS=2 PORT=50076 SURF=2 ROLLS=2 RATE=1 BAR=0.10 \
  CKPT=$CKPT JAR=$JAR ABIL=$ABIL SEED=20260916 bash scripts/build3_surface_labels.sh
RUN=$(ls -dt "$REPO"/data/runs/b4-tgt-smoke-* 2>/dev/null | head -1)
log "smoke harness done: $(cat $OUT/smoke/DONE 2>/dev/null)"
uv run python scripts/build3_label_read.py --run "$RUN" --abilities "$ABIL" > "$OUT/smoke-read.txt" 2>&1
log "smoke read -> $OUT/smoke-read.txt ($(grep -c . $OUT/smoke-read.txt) lines)"
log "smoke census: playTriggerTargets $(cat $RUN/workers/inv-*/census.jsonl | grep -c '"playTriggerTargets"') rows, target sub-rows $(grep -c '^| target' $OUT/smoke-read.txt)"
if [[ -z "${SKIP_FC:-}" ]]; then
  log "forkcheck start jar=$JAR"
  N_GAMES=500 SEED=20260703 JAR="$JAR" bash scripts/forkcheck/run_forkcheck.sh "$FC" | tee -a "$OUT/queue.log"
  pid=$(cat "$FC/run.pid"); until [ ! -d /proc/$pid ] || { [ -f "$FC/results.jsonl" ] && [ "$(wc -l < "$FC/results.jsonl")" -ge 500 ]; }; do sleep 60; done
  uv run python scripts/forkcheck/compare.py "$FC" | tee "$FC/compare.txt" | tee -a "$OUT/queue.log"
  log "forkcheck compared (read compare.txt)"
fi
echo OK > "$OUT/DONE"
python3 -c "from anvil.training.notify import notify; notify('anvil build4 targets queue DONE', '$OUT')"
