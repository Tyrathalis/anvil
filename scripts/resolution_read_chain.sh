#!/usr/bin/env bash
# THE RUNG 1' RESOLUTION READ (10-01; the running record's plan after rung 1', step 2): fresh network-alone
# reads of the un-anchored winner (shakedown-alloc/iter-019) and the weight-0.1 anchored head
# (settings-anchor-w01/iter-017) on the certmerge jar, on ONE seed set (paired), ~5,000 games each
# (2,500 per seat assignment, 24 workers x 2 servers, raw — no Ante). The pre-registered margin
# (FIXED 10-01 by the user before any game): anchor-w01 is non-inferior if anchor-w01 - alloc >= -1.0pp
# on the point estimate of the fresh paired difference. The fresh alloc read is the one OF RECORD (the
# 0.5405 was the best of four 2,000-game reads); the earlier reads are reported beside it, not pooled.
# A NEW seed base (20261001) so neither read replays the cells' 2,000-game seeds; --games-per-pair 13
# on the 200-pair file (index i plays pair (i / gpp) % 200) so every pair gets 12-13 games per seat.
# Launch: uv run python -m anvil.runs launch --name resolution-read --dir data/runs/resolution-read \
#           --watch 'data/runs/rr-*' --stall-min 60 -- bash scripts/resolution_read_chain.sh
#   env: JAR, WORKERS (24), READ_GAMES (2500 / seat), GPP (13), SEED_BASE (20261001)
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/resolution-read; mkdir -p "$OUT"
JAR=${JAR:-$REPO/data/runs/certmerge/forge-certmerge.jar}
WORKERS=${WORKERS:-24}; READ_GAMES=${READ_GAMES:-2500}; GPP=${GPP:-13}; SEED_BASE=${SEED_BASE:-20261001}
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
declare -A CKPT=(
  [alloc]=data/training/shakedown-alloc/iter-019/train/last.pt
  [anchor-w01]=data/training/settings-anchor-w01/iter-017/train/last.pt
)
[[ -f "$OUT/read.md" ]] || printf '# The rung 1'"'"' resolution read (10-01) — fresh paired network-alone reads on the certmerge jar\n\nMargin (FIXED 10-01, user, before any game): anchor-w01 − alloc ≥ −1.0pp on the fresh paired point estimate.\nEarlier 2,000-game reads, beside not pooled: alloc 0.5405 ± 0.0111 (census jar, best of four) · anchor-w01 0.5210 ± 0.0112 (certmerge jar).\n\n| cell | ckpt | games | decisive | crashes | winrate (network alone, raw) |\n|---|---|---|---|---|---|\n' > "$OUT/read.md"
log "resolution read start jar=$JAR games=${READ_GAMES}/seat gpp=$GPP seed_base=$SEED_BASE workers=$WORKERS"
for arm in alloc anchor-w01; do
  if [[ -f "$OUT/$arm.read.done" ]]; then log "cell $arm read done already"; continue; fi
  log "cell $arm: the read on ${CKPT[$arm]}"
  nice -n 19 uv run python scripts/final_read.py --ckpt "${CKPT[$arm]}" --name "rr-$arm" --games "$READ_GAMES" \
    --games-per-pair "$GPP" --seed-base "$SEED_BASE" --workers "$WORKERS" --port 50086 --servers 0 \
    --jar "$JAR" --skip-ante >> "$OUT/$arm.read.log" 2>&1 || { log "cell $arm read FAILED"; exit 1; }
  ls -dt data/runs/rr-${arm}arm-s0-* | head -1 | tr -d '\n' > "$OUT/$arm.read.done"; echo -n "," >> "$OUT/$arm.read.done"; ls -dt data/runs/rr-${arm}arm-s1-* | head -1 >> "$OUT/$arm.read.done"
  uv run python scripts/arms_report.py --arm "$arm=$(cat $OUT/$arm.read.done)" --out "$OUT/$arm.read.json" > /dev/null 2>&1
  python3 -c "
import json; r=json.load(open('$OUT/$arm.read.json'))['$arm']
print(f\"| $arm | ${CKPT[$arm]} | {r['games']} | {r['decisive']} | {r['crashes']} | {r['winrate']:.4f} ± {r['se']:.4f} |\")" >> "$OUT/read.md"
  log "cell $arm read CLOSED: $(tail -1 $OUT/read.md)"
done
log "paired difference (anchor-w01 − alloc)"
uv run python scripts/paired_arms.py --a "$(cat $OUT/anchor-w01.read.done)" --b "$(cat $OUT/alloc.read.done)" 2>&1 | tee "$OUT/paired.txt" | tee -a "$OUT/queue.log"
printf '\nPaired difference (anchor-w01 − alloc), scripts/paired_arms.py:\n\n```\n%s\n```\n' "$(cat $OUT/paired.txt)" >> "$OUT/read.md"
log "resolution read chain done"; echo OK > "$OUT/DONE"
