#!/usr/bin/env bash
# THE ERA BRIDGE (M13 Build 0 step 2; m13-plan.md, ADR-0128): the checkpoint of record and the era
# reference against the plain heuristic on the MERGED jar, on the 11-07 confirm's seeds, network alone,
# masked, raw, served with the extended ability table. The old-jar side is on file (the 11-07 confirm's
# arms, OLD_A / OLD_B); an optional short re-run of it (REP_GAMES per seat) checks that the old jar still
# reproduces those arms on today's box. The read: each checkpoint new jar minus old jar, paired on seed.
# Kill condition (pre-registered): CKPT more than 3pp below its old-jar figure.
# Idempotent on relaunch (the .done markers).
# Launch:
#   uv run python -m anvil.runs launch --name era-bridge --dir data/runs/era-bridge \
#     --launched-by '<ListAgents name> [<ref>]' --watch 'data/runs/eb-*' --stall-min 120 -- bash scripts/m13_era_bridge.sh
#   env: CKPT, REF, JAR (merged), OLD_JAR, ABIL (table stem for the merged jar), SEED_BASE, GAMES (per seat),
#        REP_GAMES (per seat, 0 = skip), OLD_A / OLD_B (the old-jar arms of CKPT / REF), WORKERS
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
CKPT=${CKPT:-data/training/big-run/iter-405/train/last.pt}
REF=${REF:-data/training/d6-run11/iter-019/train/last.pt}
JAR=${JAR:-$REPO/data/runs/merge-20261118/forge-merge-20261118-copier.jar}
OLD_JAR=${OLD_JAR:-$REPO/data/runs/tgtmask/forge-tgtmask3.jar}
ABIL=${ABIL:-data/embeddings/abil-cf2ca6ba-m13-qwen3}
SEED_BASE=${SEED_BASE:-20261107}; GAMES=${GAMES:-2500}; REP_GAMES=${REP_GAMES:-500}; WORKERS=${WORKERS:-24}
OLD_A=${OLD_A:-data/runs/bc-seg4arm-s0-20261107-063404,data/runs/bc-seg4arm-s1-20261107-071942}
OLD_B=${OLD_B:-data/runs/bc-ref-seg4arm-s0-20261107-080249,data/runs/bc-ref-seg4arm-s1-20261107-084441}
OUT=$REPO/data/runs/era-bridge; mkdir -p "$OUT"
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
read_na() { # <tag> <ckpt> <jar> <games> [server args] -> $OUT/<tag>.done (the two arm dirs)
  local tag=$1 ckpt=$2 jar=$3 games=$4 sargs=${5:-}
  [[ -f "$OUT/$tag.done" ]] && return 0
  log "read $tag network-alone: ckpt=$ckpt games=$games/seat seed_base=$SEED_BASE jar=$jar server-args='$sargs'"
  nice -n 19 uv run python scripts/final_read.py --ckpt "$ckpt" --name "eb-$tag" --games "$games" --games-per-pair 5 \
    --seed-base "$SEED_BASE" --workers "$WORKERS" --port 50086 --servers 0 --jar "$jar" --skip-ante \
    ${sargs:+--server-args "$sargs"} >> "$OUT/$tag.log" 2>&1 || { log "read $tag FAILED"; return 1; }
  ls -dt "data/runs/eb-${tag}arm-s0-"* | head -1 | tr -d '\n' > "$OUT/$tag.done"; echo -n "," >> "$OUT/$tag.done"; ls -dt "data/runs/eb-${tag}arm-s1-"* | head -1 >> "$OUT/$tag.done"
}
winrate() { uv run python scripts/arms_report.py --arm "$1=$2" --out "$OUT/$1.json" 2>/dev/null | grep -o "winrate [0-9.]* ± [0-9.]*" | head -1; }
paired() { uv run python scripts/paired_arms.py --a "$1" --b "$2" 2>&1 | tee "$OUT/$3.paired.txt" | grep -o 'A - B: [^)]*)' | head -1; }
log "era bridge: ckpt=$CKPT ref=$REF jar=$JAR old_jar=$OLD_JAR abil=$ABIL seed_base=$SEED_BASE games=$GAMES/seat rep=$REP_GAMES/seat"
if (( REP_GAMES > 0 )); then read_na "oldrep" "$CKPT" "$OLD_JAR" "$REP_GAMES" || exit 1; fi
read_na "new" "$CKPT" "$JAR" "$GAMES" "--abilities $ABIL" || exit 1
read_na "ref-new" "$REF" "$JAR" "$GAMES" "--abilities $ABIL" || exit 1
NEW_A=$(cat "$OUT/new.done"); NEW_B=$(cat "$OUT/ref-new.done")
{
  echo "# The era bridge (M13 Build 0 step 2): seeds $SEED_BASE, $GAMES / seat, network alone, masked, raw"
  echo
  echo "| arm | winrate |"; echo "|---|---|"
  echo "| ckpt, old jar (on file) | $(winrate old "$OLD_A") |"
  echo "| ckpt, merged jar | $(winrate new "$NEW_A") |"
  echo "| reference, old jar (on file) | $(winrate ref-old "$OLD_B") |"
  echo "| reference, merged jar | $(winrate ref-new "$NEW_B") |"
  echo
  echo "| paired difference | value |"; echo "|---|---|"
  echo "| ckpt: merged − old (the kill condition reads this; bar −3pp) | $(paired "$NEW_A" "$OLD_A" ckpt-new-old) |"
  echo "| reference: merged − old | $(paired "$NEW_B" "$OLD_B" ref-new-old) |"
  echo "| merged jar: ckpt − reference | $(paired "$NEW_A" "$NEW_B" new-ckpt-ref) |"
  echo "| old jar: ckpt − reference (on file) | $(paired "$OLD_A" "$OLD_B" old-ckpt-ref) |"
  if (( REP_GAMES > 0 )); then
    echo "| old jar re-run − old jar on file, first $REP_GAMES / seat | $(paired "$(cat "$OUT/oldrep.done")" "$OLD_A" oldrep) |"
  fi
} > "$OUT/bridge.md"
log "era bridge done"; cat "$OUT/bridge.md" | tee -a "$OUT/queue.log"; echo OK > "$OUT/DONE"
