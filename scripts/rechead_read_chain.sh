#!/usr/bin/env bash
# The segment-3 boundary's HEAD-TRANSPLANT with-lookahead read (running record 10-29; exploratory, for the
# anchor-arm ADR): iter-301's weights with settings-recovery/iter-006's value head (Spearman 0.4087 vs 0.3263 on
# the bank; data/training/big-run/iter-301-rechead) under RECIPE + the checkpoint's alloc tau, 500 games / seat on
# seed base 20261006 so it pairs game-for-game with brla-seg3 — the search's worth with a better-ranking leaf on
# the same trunk. Network-alone is identical by construction (the value head does not act). Waits for the rolls-4
# read's DONE. Launch: anvil.runs launch --name rechead-read --dir data/runs/rechead-read
#   --watch 'data/runs/brla-seg3rh*' -- bash scripts/rechead_read_chain.sh
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/rechead-read; mkdir -p "$OUT"
CKPT=data/training/big-run/iter-301-rechead/train/last.pt; JAR=$REPO/data/runs/tgtmask/forge-tgtmask3.jar; SB=20261006; GAMES=500; WORKERS=24
source scripts/recipe.sh
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "waiting for the rolls-4 read (data/runs/rolls4-read/DONE)"
until [[ -f data/runs/rolls4-read/DONE ]]; do sleep 120; done
tau=$(uv run python -c "from anvil.training.selfplay import alloc_tau_of; t=alloc_tau_of('$CKPT'); print('' if t is None else f'{t:.5f}')" 2>/dev/null | tail -1)
fa="$RECIPE"; [[ -n "$tau" ]] && fa="$fa -searchalloc $tau -searchfloor 0.1"
log "read seg3 rechead: ckpt=$CKPT games=$GAMES/seat seed_base=$SB forge_args='$fa'"
if [[ ! -f "$OUT/seg3rh.la.done" ]]; then
  nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT" --name "brla-seg3rh" --games "$GAMES" --games-per-pair 5 \
    --seed-base "$SB" --workers "$WORKERS" --port 50086 --servers 0 --jar "$JAR" --skip-ante --forge-args "$fa" --labels >> "$OUT/seg3rh.la.log" 2>&1 \
    || { log "read FAILED"; exit 1; }
  ls -dt "data/runs/brla-seg3rharm-s0-"* | head -1 | tr -d '\n' > "$OUT/seg3rh.la.done"; echo -n "," >> "$OUT/seg3rh.la.done"; ls -dt "data/runs/brla-seg3rharm-s1-"* | head -1 >> "$OUT/seg3rh.la.done"
fi
W=$(uv run python scripts/arms_report.py --arm "seg3rh=$(cat $OUT/seg3rh.la.done)" --out "$OUT/seg3rh.la.json" 2>/dev/null | grep -o "winrate [0-9.]* ± [0-9.]*" | head -1)
P=$(uv run python scripts/paired_arms.py --a "$(cat $OUT/seg3rh.la.done)" --b "$(cat data/runs/big-run/seg3.la.done)" 2>&1 | tee "$OUT/seg3rh.paired.txt" | grep -o 'A - B: [^)]*)' | head -1)
{ echo "# The segment-3 boundary head-transplant read (10-29): iter-301 + the recovery value head, with-lookahead (rolls 2) vs the segment read's own head, 500 games/seat, seed base $SB, masked, raw"; echo; echo "| arm | with-lookahead |"; echo "|---|---|"; echo "| recovery head (bank Spearman 0.4087) | $W |"; echo "| own head (brla-seg3; 0.3263) | winrate 0.6100 ± 0.0154 |"; echo; echo "paired rechead - own: $P"; echo; echo "Exploratory (the anchor-arm ADR): the search's worth with a better-ranking leaf on the same trunk."; } > "$OUT/read.md"
log "DONE: $W | paired $P"; echo OK > "$OUT/DONE"
