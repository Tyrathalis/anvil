#!/usr/bin/env bash
# THE PROMOTION READ OF AN ARM'S FINAL CHECKPOINT (M13 Build 3; ADR-0135, second addendum).
# Three reads, network alone, each on iter-405's seeds and paired game for game with iter-405's arms on file:
#   plain   against the plain heuristic, 2,500 games per seat on the 11-07 confirm's seeds. THE GATE:
#           the paired difference against iter-405 above 2 standard errors.
#   mc      against the Monte Carlo heuristic at 8 rounds, the same seeds (ADR-0129). Beside the gate.
#   precon  on held-out Commander precons with the extended card table, new cards on the no-card id row
#           (ADR-0130). Beside the gate.
# A paired loss of more than 2 standard errors on mc or precon holds the promotion for the user.
# Idempotent on relaunch (the .done markers). Report: $OUT/promo.md.
# Launch:
#   uv run python -m anvil.runs launch --name m13-promo-<tag> --dir data/runs/m13-promo/<tag> --quiet-box \
#     --launched-by '<ListAgents name> [<ref>]' --watch 'data/runs/promo-<tag>*' --stall-min 120 \
#     -- bash scripts/m13_promo_read.sh <tag> <ckpt>
#   env: JAR, GAMES (per seat), WORKERS, STAGES
set -u
TAG=${1:?tag, e.g. ctl}; CKPT=${2:?final checkpoint path}
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
JAR=${JAR:-$REPO/data/runs/m13-build2/forge-b2-mcguard.jar}
GAMES=${GAMES:-2500}; WORKERS=${WORKERS:-24}; STAGES=${STAGES:-"plain mc precon"}
ABIL=data/embeddings/abil-cf2ca6ba-m13-qwen3
# iter-405's arms on file
REF_PLAIN=data/runs/eb-newarm-s0-20261118-184910,data/runs/eb-newarm-s1-20261118-192149
REF_MC=data/runs/mcckarm-s0-20261119-094359,data/runs/mcckarm-s1-20261119-122331
REF_PC=data/runs/pc-idnullarm-s0-20261119-165746,data/runs/pc-idnullarm-s1-20261119-172649
PC=$REPO/data/runs/m13-precon; PC_VERSION=precon-620a4be5
OUT=${OUT_DIR:-$REPO/data/runs/m13-promo/$TAG}; mkdir -p "$OUT"
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
arms_of() { echo "$(ls -dt "data/runs/${1}arm-s0-"* | head -1),$(ls -dt "data/runs/${1}arm-s1-"* | head -1)"; }
winrate() { uv run python scripts/arms_report.py --arm "$1=$2" --out "$OUT/$1.json" 2>/dev/null | grep -o "winrate [0-9.]* ± [0-9.]*" | head -1; }
paired() { uv run python scripts/paired_arms.py --a "$2" --b "$3" 2>&1 | tee "$OUT/$1.paired.txt" | grep -o 'A - B: [^)]*)' | head -1; }

log "promotion read: tag=$TAG ckpt=$CKPT jar=$JAR games=$GAMES/seat stages='$STAGES'"
[[ -f "$CKPT" ]] || { log "no checkpoint at $CKPT"; exit 2; }
for s in $STAGES; do
  case "$s" in
    plain)
      if [[ ! -f "$OUT/plain.done" ]]; then
        log "plain: against the plain heuristic, seeds 20261107"
        nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT" --name "promo-$TAG" --games "$GAMES" --games-per-pair 5 \
          --seed-base 20261107 --workers "$WORKERS" --port 50086 --servers 0 --jar "$JAR" --skip-ante \
          --server-args "--abilities $ABIL" >> "$OUT/plain.log" 2>&1 || { log "plain FAILED"; exit 1; }
        arms_of "promo-$TAG" > "$OUT/plain.done"
      fi ;;
    mc)
      if [[ ! -f "$OUT/mc.done" ]]; then
        log "mc: against the Monte Carlo heuristic at 8 rounds, seeds 20261107"
        env ROUNDS=8 CKPT="$CKPT" ABIL="$ABIL" TAG="promo-$TAG-mc" OUT_DIR="$OUT/mc" JAR="$JAR" GAMES="$GAMES" WORKERS="$WORKERS" \
          PLAIN_ARMS="$(cat "$OUT/plain.done" 2>/dev/null || echo "$REF_PLAIN")" \
          ANVIL_EXTRA_JVM_OPTS="-Danvil.crash.trace=true -Xmx3g" bash scripts/m13_mc.sh ckpt >> "$OUT/mc.log" 2>&1 \
          || { log "mc FAILED"; exit 1; }
        cp "$OUT/mc/promo-$TAG-mc.done" "$OUT/mc.done"
      fi ;;
    precon)
      if [[ ! -f "$OUT/precon.done" ]]; then
        PCK="$OUT/ckpt-$PC_VERSION-idnull.pt"
        if [[ ! -f "$PCK" ]]; then
          log "precon: extending the card table of $CKPT"
          uv run python scripts/m13_precon_table.py --ckpt "$CKPT" --names "$PC/precon-names.txt" --tag precon \
            --out-dir "$OUT" >> "$OUT/precon-table.log" 2>&1 || { log "precon table FAILED"; exit 1; }
          [[ -f "$PCK" ]] || { log "precon table wrote no $PCK"; exit 1; }
        fi
        log "precon: held-out precons, seeds 20261121"
        nice -n 19 uv run python scripts/final_read.py --ckpt "$PCK" --name "promo-$TAG-pc" --games "$GAMES" --games-per-pair 5 \
          --seed-base 20261121 --workers "$WORKERS" --port 50086 --servers 0 --jar "$JAR" --skip-ante \
          --pairs-file "$PC/pairs.txt" --pool-version "$PC_VERSION" \
          --server-args "--abilities data/embeddings/abil-precon-m13-qwen3" >> "$OUT/precon.log" 2>&1 \
          || { log "precon FAILED"; exit 1; }
        arms_of "promo-$TAG-pc" > "$OUT/precon.done"
      fi ;;
    *) log "unknown stage $s"; exit 2 ;;
  esac
done

{
  echo "# Promotion read: $CKPT"
  echo
  echo "Network alone, $GAMES games per seat, jar $(basename "$JAR"). Each difference is paired game for game with iter-405's arm on file."
  echo
  echo "| read | this checkpoint | iter-405 on file | paired difference |"
  echo "|---|---|---|---|"
  for row in "plain:$REF_PLAIN" "mc:$REF_MC" "precon:$REF_PC"; do
    s=${row%%:*}; ref=${row#*:}
    [[ -f "$OUT/$s.done" ]] || continue
    a=$(cat "$OUT/$s.done")
    echo "| $s | $(winrate "$s" "$a") | $(winrate "$s-ref" "$ref") | $(paired "$s" "$a" "$ref") |"
  done
} > "$OUT/promo.md" 2>&1
cat "$OUT/promo.md" | tee -a "$OUT/queue.log"
log "promotion read done"; echo OK > "$OUT/DONE"
