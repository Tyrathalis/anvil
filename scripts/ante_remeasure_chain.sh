#!/usr/bin/env bash
# THE ANTE RE-MEASURE (ADR-0119 step 2, ADR-0121 §4; 10-03): one 2,000-game read serves both
# step-2 halves — the games generate on the SHUFFLE-MARK jar (fork 8d82dfa546, forkcheck PASS) with
# the rung-2 checkpoint of record (settings-stopgrad-t3e6/iter-019) network alone, obs + census on;
# final_read's own Ante step scores the ledger with the standing full-vis critic (d4-critic-fullvis),
# then a second certify pass scores the SAME stores with the stopgrad head itself on omniscient
# windows (certify --full-vis). Read of record: corr(raw, ledger) and the effective-sample ratio
# per critic, shuffle_cleanse beside draw_poisoned in the census; the 1.5x bar (ADR-0119 step 3)
# decides whether corrected reads become the number of record. Exploratory beyond that bar.
#   env: CKPT, JAR (the shufflemark snapshot), WORKERS (24), READ_GAMES per seat (1000), SEED_BASE (20261003)
# Launch (box quiet, after the forkcheck's PASS):
#   uv run python -m anvil.runs launch --name ante-remeasure --dir data/runs/ante-remeasure \
#     --watch 'data/runs/ar-*' --stall-min 60 -- bash scripts/ante_remeasure_chain.sh
set -u
REPO=${REPO:-/home/tyrathalis/Everything/Projects/Anvil}; cd "$REPO"
OUT=${OUT:-$REPO/data/runs/ante-remeasure}; mkdir -p "$OUT"
CKPT=${CKPT:-data/training/settings-stopgrad-t3e6/iter-019/train/last.pt}
JAR=${JAR:-$REPO/data/runs/shufflemark/forge-shufflemark.jar}
CRITIC=${CRITIC:-data/training/d4-critic-fullvis/last.pt}
WORKERS=${WORKERS:-24}; READ_GAMES=${READ_GAMES:-1000}; GPP=${GPP:-5}; SEED_BASE=${SEED_BASE:-20261003}
NAME=ar-stopgrad
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
[[ -f "$JAR" ]] || { log "no jar at $JAR"; exit 1; }
log "re-measure start ckpt=$CKPT jar=$JAR critic=$CRITIC games=${READ_GAMES}/seat gpp=$GPP seed_base=$SEED_BASE"
if [[ ! -f "$OUT/read.done" ]]; then
  nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT" --name "$NAME" --games "$READ_GAMES" \
    --games-per-pair "$GPP" --seed-base "$SEED_BASE" --workers "$WORKERS" --port 50088 --servers 0 \
    --jar "$JAR" --critic "$CRITIC" >> "$OUT/read.log" 2>&1 || { log "read FAILED"; exit 1; }
  ls -dt data/runs/${NAME}arm-s0-* | head -1 | tr -d '\n' > "$OUT/read.done"; echo -n "," >> "$OUT/read.done"; ls -dt data/runs/${NAME}arm-s1-* | head -1 >> "$OUT/read.done"
fi
log "read done: $(cat $OUT/read.done)"
# the second critic: the stopgrad head itself, omniscient windows, over the same stores
for rd in $(tr ',' ' ' < "$OUT/read.done"); do
  arm=$(basename "$rd"); rep="$OUT/ante-head-$arm.json"
  if [[ ! -f "$rep" ]]; then
    log "head-as-critic certify on $arm"
    nice -n 19 uv run python -m anvil.ante.certify --store "data/trajectories/$arm" --ckpt "$CKPT" --full-vis \
      --out "$rep" --ledger-out "$rep.ledger.jsonl" >> "$OUT/certify-head.log" 2>&1 || { log "head certify FAILED on $arm"; exit 1; }
  fi
done
log "summary"
uv run python scripts/ante_remeasure.py --read-done "$OUT/read.done" --out-dir "$OUT" --critic-name d4-critic-fullvis \
  --head-ckpt "$CKPT" | tee -a "$OUT/queue.log" > "$OUT/read.md" || { log "summary FAILED"; exit 1; }
log "re-measure done: $(grep -m1 -o 'effective-sample.*' $OUT/read.md)"; echo OK > "$OUT/DONE"
