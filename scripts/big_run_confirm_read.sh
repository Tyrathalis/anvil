#!/usr/bin/env bash
# THE CONFIRMING PAIRED READ for a promotion read mid-run (ADR-0123 §4 / §5; first used at segment 1's close,
# 10-13): the segment's final checkpoint and the ERA REFERENCE d6-run11/iter-019, each 2,500 games per seat
# (5,000 games) on FRESH seeds (SEED_BASE), network-alone, the launch jar, the decoder masked, raw; then the
# game-for-game paired difference (SE ≈ 0.7pp) and both arms' raw winrates. The promotion clause reads on the
# paired number: ≥ +2.5pp confirms the segment read's bar; the promotion itself is the user's call (a
# state-of-record change). Idempotent on relaunch (the .done markers). ≈ 10,000 games ≈ 4 h at 24 workers.
# Launch (the box quiet, the run `done` between segments):
#   uv run python -m anvil.runs launch --name big-run-confirm --dir data/runs/big-run-confirm \
#     --launched-by '<ListAgents name> [<ref>]' --watch 'data/runs/bc*' --stall-min 120 -- bash scripts/big_run_confirm_read.sh
#   env: CKPT (the segment's final ckpt), TAG (seg1), SEED_BASE (20261013), GAMES (2500 / seat), REF, JAR, WORKERS
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
TAG=${TAG:-seg1}
CKPT=${CKPT:-data/training/big-run/iter-099/train/last.pt}
REF=${REF:-data/training/d6-run11/iter-019/train/last.pt}
JAR=${JAR:-$REPO/data/runs/tgtmask/forge-tgtmask3.jar}
SEED_BASE=${SEED_BASE:-20261013}; GAMES=${GAMES:-2500}; WORKERS=${WORKERS:-24}
OUT=$REPO/data/runs/big-run-confirm; mkdir -p "$OUT"
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
read_na() { # <tag> <ckpt> -> $OUT/<tag>.na.done (the two arm dirs)
  local tag=$1 ckpt=$2
  [[ -f "$OUT/$tag.na.done" ]] && return 0
  log "read $tag network-alone: ckpt=$ckpt games=$GAMES/seat seed_base=$SEED_BASE"
  nice -n 19 uv run python scripts/final_read.py --ckpt "$ckpt" --name "bc-$tag" --games "$GAMES" --games-per-pair 5 \
    --seed-base "$SEED_BASE" --workers "$WORKERS" --port 50086 --servers 0 --jar "$JAR" --skip-ante >> "$OUT/$tag.na.log" 2>&1 \
    || { log "read $tag FAILED"; return 1; }
  ls -dt "data/runs/bc-${tag}arm-s0-"* | head -1 | tr -d '\n' > "$OUT/$tag.na.done"; echo -n "," >> "$OUT/$tag.na.done"; ls -dt "data/runs/bc-${tag}arm-s1-"* | head -1 >> "$OUT/$tag.na.done"
}
winrate() { uv run python scripts/arms_report.py --arm "$1=$(cat "$2")" --out "${2%.done}.json" 2>/dev/null | grep -o "winrate [0-9.]* ± [0-9.]*" | head -1; }
log "confirming paired read $TAG: ckpt=$CKPT ref=$REF seed_base=$SEED_BASE games=$GAMES/seat jar=$JAR"
read_na "$TAG" "$CKPT" || exit 1
read_na "ref-$TAG" "$REF" || exit 1
PAIRED=$(uv run python scripts/paired_arms.py --a "$(cat $OUT/$TAG.na.done)" --b "$(cat $OUT/ref-$TAG.na.done)" 2>&1 | tee "$OUT/$TAG.paired.txt" | grep -o 'A - B: [^)]*)' | head -1)
W=$(winrate "$TAG" "$OUT/$TAG.na.done"); R=$(winrate "ref-$TAG" "$OUT/ref-$TAG.na.done")
[[ -f "$OUT/confirm.md" ]] || printf '# The confirming paired reads (ADR-0123 §4): fresh seeds, 2,500 / seat, network-alone, masked, raw\n\n| segment | ckpt | ckpt winrate | era reference winrate | ckpt − reference (paired) | seed base |\n|---|---|---|---|---|---|\n' > "$OUT/confirm.md"
printf '| %s | %s | %s | %s | %s | %s |\n' "$TAG" "$CKPT" "$W" "$R" "$PAIRED" "$SEED_BASE" >> "$OUT/confirm.md"
printf '| confirm %s (fresh seeds %s, 2,500 / seat) |  |  |  | %s | %s |  | %s |  |  |\n' "$TAG" "$SEED_BASE" "$CKPT" "$W" "$PAIRED" >> "$REPO/data/runs/big-run/read.md"
log "confirming read $TAG done: ckpt $W | reference $R | $PAIRED"; echo OK > "$OUT/$TAG.DONE"
