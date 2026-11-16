#!/usr/bin/env bash
# THE TWO READS AFTER SEGMENT 5 (the user's call 11-15; m12-running-record.md, 11-15), on the quiet box:
#   1. the HEAD-TO-HEAD read (the 11-09 design review's finding 3): the ckpt of record big-run/iter-405 against
#      the WARM START shakedown-alloc/iter-019, both seats bridged, network-alone, the launch jar, masked
#      (scripts/h2h_read.py; H2H_GAMES per seat assignment on H2H_SEED_BASE).
#   2. the final checkpoint big-run/iter-513 at 2,500 per seat on the 11-07 confirm's seeds (20261107), so that
#      it pairs game-for-game with the iter-405 and era-reference arms that confirm already holds. No new
#      reference games: the reference's marker for this tag is the 11-07 one. This stands in for the scripted
#      close (CLOSE=1), which would read iter-513 on a seed set no other checkpoint was read on. The seeds are
#      not fresh for the run, but iter-513 was never selected on them.
# Idempotent on relaunch (the .done markers and the head-to-head's report file).
# Launch:
#   uv run python -m anvil.runs launch --name big-run-post5 --dir data/runs/big-run-post5 \
#     --launched-by '<ListAgents name> [<ref>]' --watch 'data/runs/h2h*' --watch 'data/runs/bc*' \
#     --watch 'data/runs/big-run-confirm' --stall-min 120 -- bash scripts/big_run_post5_reads.sh
#   env: A, B, H2H_GAMES (2500 / seat), H2H_SEED_BASE (20261115), FINAL, JAR, WORKERS (24)
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
A=${A:-data/training/big-run/iter-405/train/last.pt}
B=${B:-data/training/shakedown-alloc/iter-019/train/last.pt}
FINAL=${FINAL:-data/training/big-run/iter-513/train/last.pt}
JAR=${JAR:-$REPO/data/runs/tgtmask/forge-tgtmask3.jar}
H2H_GAMES=${H2H_GAMES:-2500}; H2H_SEED_BASE=${H2H_SEED_BASE:-20261115}; WORKERS=${WORKERS:-24}
OUT=$REPO/data/runs/big-run-post5; CONF=$REPO/data/runs/big-run-confirm; mkdir -p "$OUT"
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }

# ---- 1. the head-to-head ----
H2H=$REPO/data/runs/h2h-405-start-h2h.json
if [[ ! -f "$H2H" ]]; then
  log "head-to-head: A=$A B=$B games=$H2H_GAMES/seat seed_base=$H2H_SEED_BASE jar=$JAR"
  uv run python scripts/h2h_read.py --a "$A" --b "$B" --name h2h-405-start --games "$H2H_GAMES" \
    --seed-base "$H2H_SEED_BASE" --workers "$WORKERS" --port 50086 --jar "$JAR" >> "$OUT/h2h.log" 2>&1 \
    || { log "head-to-head FAILED"; exit 1; }
fi
log "head-to-head done: $(grep -o 'A score.*' "$OUT/h2h.log" | tail -1)"

# ---- 2. iter-513 on the 11-07 confirm's seeds, paired with the arms already there ----
[[ -f "$CONF/seg4.na.done" && -f "$CONF/ref-seg4.na.done" ]] || { log "the 11-07 confirm's arms are missing"; exit 1; }
[[ -f "$CONF/ref-seg5.na.done" ]] || cp "$CONF/ref-seg4.na.done" "$CONF/ref-seg5.na.done"   # the same reference games
if [[ ! -f "$CONF/seg5.DONE" ]]; then
  log "iter-513 on seed base 20261107, 2,500/seat: ckpt=$FINAL"
  TAG=seg5 CKPT="$FINAL" SEED_BASE=20261107 GAMES=2500 JAR="$JAR" WORKERS="$WORKERS" \
    bash scripts/big_run_confirm_read.sh >> "$OUT/confirm.log" 2>&1 || { log "iter-513 read FAILED"; exit 1; }
fi
P405=$(uv run python scripts/paired_arms.py --a "$(cat "$CONF/seg5.na.done")" --b "$(cat "$CONF/seg4.na.done")" 2>&1 \
  | tee "$OUT/seg5-vs-seg4.paired.txt" | grep -o 'A - B: [^)]*)' | head -1)
log "iter-513 read done: $(tail -1 "$CONF/confirm.md")"
log "iter-513 − iter-405 on seed base 20261107 (paired): $P405"
echo OK > "$OUT/DONE"
