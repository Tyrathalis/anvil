#!/usr/bin/env bash
# ADR-0110 (the 2026-09-16 upstream merge): the boundary's reference reads on
# the merged jar snapshot (JAR), after the flag-off baseline forkcheck has
# landed (500 rows in BASE/results.jsonl):
#   ref   iter-019 (the ckpt of record) vs the heuristic — the standard
#         2,000-game read WITH the Ante certify (the era's new reference
#         number; the era-scoped Ante maps refit from these arms, ADR-0036)
#   heur  the heuristic mirror (--heuristic-control, --skip-ante) — the
#         symmetry check + the reference population for the pool's statistics
# Launched through anvil.runs (its dir = OUT). env: WORKERS (24), PORT (50065).
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=${OUT:-$REPO/data/runs/merge-boundary}; mkdir -p "$OUT"
JAR=${JAR:-$OUT/forge-merge-1db054ade4.jar}
BASE=${BASE:-$REPO/data/forkcheck/run-20260916-merge-baseline}
CKPT_REF=${CKPT_REF:-data/training/d6-run11/iter-019/train/last.pt}
GAMES=${GAMES:-1000}; WORKERS=${WORKERS:-24}; PORT=${PORT:-50065}; NAME=${NAME:-merge}
export PYTHONUNBUFFERED=1 DISPLAY=:0
export XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1)
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/reads.log"; }
arms_of() { ls -dt data/runs/${1}arm-s0-* | head -1 | tr -d '\n'; echo -n ","; ls -dt data/runs/${1}arm-s1-* | head -1; }

log "waiting for the baseline forkcheck ($BASE)"
until [ "$(wc -l < "$BASE/results.jsonl" 2>/dev/null || echo 0)" -ge 500 ]; do sleep 60; done
log "baseline landed; reads start on jar=$JAR"

if [[ ! -f "$OUT/ref.done" ]]; then
  log "arm ref (iter-019 vs heuristic, Ante certify on) start"
  nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT_REF" --name "$NAME-ref" --games "$GAMES" \
      --workers "$WORKERS" --port "$PORT" --jar "$JAR" >> "$OUT/ref.log" 2>&1 || { log "arm ref FAILED"; exit 1; }
  arms_of "$NAME-ref" > "$OUT/ref.done"; log "arm ref done: $(cat $OUT/ref.done)"
fi
if [[ ! -f "$OUT/heur.done" ]]; then
  log "arm heur (the heuristic mirror) start"
  nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT_REF" --name "$NAME-heur" --games "$GAMES" \
      --workers "$WORKERS" --port "$PORT" --jar "$JAR" --skip-ante --heuristic-control >> "$OUT/heur.log" 2>&1 || { log "arm heur FAILED"; exit 1; }
  arms_of "$NAME-heur" > "$OUT/heur.done"; log "arm heur done: $(cat $OUT/heur.done)"
fi
log "reads done (ref: $(cat $OUT/ref.done); heur: $(cat $OUT/heur.done)) — read the final_read reports in ref.log / heur.log"
