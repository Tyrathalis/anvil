#!/usr/bin/env bash
# The iteration-239 event's strength read (running record 10-26, pre-registered): paired network-alone, iter-291 vs
# iter-289 (the last quiet checkpoint), 1,000 games per seat each on fresh seeds, the arms-read style via
# final_read.py; waits for the big run's pause before touching the GPU. Verdict line: the slide is real if
# iter291 - iter289 <= -1.5pp.
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/event-read2; mkdir -p "$OUT"
JAR=$REPO/data/runs/tgtmask/forge-tgtmask3.jar; SB=20261028; GAMES=1000; WORKERS=24
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
state() { python3 -c "import json;print(json.load(open('/home/tyrathalis/.local/state/anvil/runs/big-run.json')).get('state'))"; }
log "waiting for the big run to leave 'running' (the pause at the 260 boundary)"
while [[ "$(state)" == running ]]; do sleep 60; done
log "big run state: $(state) — reads start"
read_na() { local tag=$1 ckpt=$2
  [[ -f "$OUT/$tag.na.done" ]] && return 0
  log "read $tag: ckpt=$ckpt games=$GAMES/seat seed_base=$SB"
  nice -n 19 uv run python scripts/final_read.py --ckpt "$ckpt" --name "br-$tag" --games "$GAMES" --games-per-pair 5 \
    --seed-base "$SB" --workers "$WORKERS" --port 50086 --servers 0 --jar "$JAR" --skip-ante >> "$OUT/$tag.na.log" 2>&1 \
    || { log "read $tag FAILED"; return 1; }
  ls -dt "data/runs/br-${tag}arm-s0-"* | head -1 | tr -d '\n' > "$OUT/$tag.na.done"; echo -n "," >> "$OUT/$tag.na.done"; ls -dt "data/runs/br-${tag}arm-s1-"* | head -1 >> "$OUT/$tag.na.done"
}
winrate() { uv run python scripts/arms_report.py --arm "$1=$(cat "$2")" --out "${2%.done}.json" 2>/dev/null | grep -o "winrate [0-9.]* ± [0-9.]*" | head -1; }
read_na ev291 data/training/big-run/iter-291/train/last.pt || exit 1
read_na ev289 data/training/big-run/iter-289/train/last.pt || exit 1
W259=$(winrate ev291 "$OUT/ev291.na.done"); W238=$(winrate ev289 "$OUT/ev289.na.done")
P=$(uv run python scripts/paired_arms.py --a "$(cat "$OUT/ev291.na.done")" --b "$(cat "$OUT/ev289.na.done")" 2>/dev/null | grep -o 'A - B: [^)]*)' | head -1)
{ echo "# The iteration-291 kl-trip read (10-28): iter-291 vs iter-289, network-alone, 1,000 games/seat, seed base $SB, masked, raw"; echo; echo "| ckpt | network-alone |"; echo "|---|---|"; echo "| iter-291 | $W259 |"; echo "| iter-289 | $W238 |"; echo; echo "paired iter291 - iter289: $P"; echo; echo "Pre-registered: the slide is real if <= -1.5pp."; } > "$OUT/read.md"
log "DONE: 259 $W259 | 238 $W238 | paired $P"; echo ok > "$OUT/DONE"
