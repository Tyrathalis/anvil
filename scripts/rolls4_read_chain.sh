#!/usr/bin/env bash
# The segment-3 boundary's rolls-4 with-lookahead read (running record 10-29; exploratory, for the anchor-arm ADR):
# iter-301 under RECIPE with -searchrolls 4 (2 -> 4) + the checkpoint's alloc tau, 500 games / seat on the segment
# read's seed base 20261006 so it pairs game-for-game with brla-seg3 (rolls 2). Waits for the confirm read's DONE
# (one read on the box at a time). Launch: anvil.runs launch --name rolls4-read --dir data/runs/rolls4-read
#   --watch 'data/runs/brla-seg3r4*' -- bash scripts/rolls4_read_chain.sh
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/rolls4-read; mkdir -p "$OUT"
CKPT=data/training/big-run/iter-301/train/last.pt; JAR=$REPO/data/runs/tgtmask/forge-tgtmask3.jar; SB=20261006; GAMES=500; WORKERS=24
source scripts/recipe.sh
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "waiting for the confirm read (data/runs/big-run-confirm/seg3.DONE)"
until [[ -f data/runs/big-run-confirm/seg3.DONE ]]; do sleep 120; done
tau=$(uv run python -c "from anvil.training.selfplay import alloc_tau_of; t=alloc_tau_of('$CKPT'); print('' if t is None else f'{t:.5f}')" 2>/dev/null | tail -1)
fa="${RECIPE/-searchrolls 2/-searchrolls 4}"; [[ -n "$tau" ]] && fa="$fa -searchalloc $tau -searchfloor 0.1"
log "read seg3 rolls-4: ckpt=$CKPT games=$GAMES/seat seed_base=$SB forge_args='$fa'"
if [[ ! -f "$OUT/seg3r4.la.done" ]]; then
  nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT" --name "brla-seg3r4" --games "$GAMES" --games-per-pair 5 \
    --seed-base "$SB" --workers "$WORKERS" --port 50086 --servers 0 --jar "$JAR" --skip-ante --forge-args "$fa" --labels >> "$OUT/seg3r4.la.log" 2>&1 \
    || { log "read FAILED"; exit 1; }
  ls -dt "data/runs/brla-seg3r4arm-s0-"* | head -1 | tr -d '\n' > "$OUT/seg3r4.la.done"; echo -n "," >> "$OUT/seg3r4.la.done"; ls -dt "data/runs/brla-seg3r4arm-s1-"* | head -1 >> "$OUT/seg3r4.la.done"
fi
W=$(uv run python scripts/arms_report.py --arm "seg3r4=$(cat $OUT/seg3r4.la.done)" --out "$OUT/seg3r4.la.json" 2>/dev/null | grep -o "winrate [0-9.]* ± [0-9.]*" | head -1)
P=$(uv run python scripts/paired_arms.py --a "$(cat $OUT/seg3r4.la.done)" --b "$(cat data/runs/big-run/seg3.la.done)" 2>&1 | tee "$OUT/seg3r4.paired.txt" | grep -o 'A - B: [^)]*)' | head -1)
{ echo "# The segment-3 boundary rolls-4 read (10-29): iter-301 with-lookahead, -searchrolls 4 vs the segment read's rolls 2, 500 games/seat, seed base $SB, masked, raw"; echo; echo "| arm | with-lookahead |"; echo "|---|---|"; echo "| rolls 4 | $W |"; echo "| rolls 2 (brla-seg3) | winrate 0.6100 ± 0.0154 |"; echo; echo "paired rolls4 - rolls2: $P"; echo; echo "Exploratory (the anchor-arm ADR): the search's worth with a deeper leaf on this trunk."; } > "$OUT/read.md"
log "DONE: $W | paired $P"; echo OK > "$OUT/DONE"
