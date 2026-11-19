#!/usr/bin/env bash
# 11-18 (ADR-0128, the M13 upstream merge): the boundary forkcheck on the merged jar, Monte Carlo
# flag off (the game flag is false unless a harness sets it; ForkFidelityCheck does not).
# Identity with the old jar is NOT expected. Three reads:
#   1. the new baseline run-20261118-merge-baseline (500 games, the standing seed set): crashes
#      and the copy-fidelity mix against the old era's 451 / 48 / 1;
#   2. its drift against the old baseline (for the record only, never a proof);
#   3. a second pass on the same jar and seeds (run-20261118-merge-repeat) against the new
#      baseline: whether the baseline reproduces, since every later tip is proven against it
#      and upstream's AI deadline is wall-clock.
# The fixed jar (the cast-payoff ValidCard fix, fork 1d4048fa2f) reruns the same chain with
#   STEM=forge-merge-20261118-fix RUN=mergefix PRIOR=data/forkcheck/run-20261118-merge-baseline
# so its baseline is compared with the unfixed merge's (how many games the fix changes).
# SINGLE=1 runs the first pass only (an ADR-0025 identity proof of a later tip against PRIOR).
# Launch:
#   uv run python -m anvil.runs launch --name merge20261118-forkcheck --dir data/runs/merge-20261118 \
#     --watch 'data/forkcheck/run-20261118-merge-*' --launched-by '<name> [<ref>]' \
#     -- bash scripts/merge20261118_forkcheck_chain.sh
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/merge-20261118; mkdir -p "$OUT"
STEM=${STEM:-forge-merge-20261118}; RUN=${RUN:-merge}
JAR=$OUT/$STEM.jar
OLD=$REPO/${PRIOR:-data/forkcheck/run-20260916-merge-baseline}
BASE=$REPO/data/forkcheck/run-20261118-$RUN-baseline
REP=$REPO/data/forkcheck/run-20261118-$RUN-repeat
export DISPLAY=${DISPLAY:-:0}
export XAUTHORITY=${XAUTHORITY:-$(ls /run/user/1000/xauth_* 2>/dev/null | head -1)}
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "chain start jar=$JAR ($(cat "$OUT/$STEM.commit"))"

pass() { # dir baseline
  local fc=$1 base=$2
  if [[ ! -f "$fc/compare.txt" ]]; then
    N_GAMES=500 SEED=20260703 JAR="$JAR" bash scripts/forkcheck/run_forkcheck.sh "$fc" | tee -a "$OUT/queue.log"
    local pid; pid=$(cat "$fc/run.pid")
    log "forkcheck detached pid=$pid dir=$fc"
    until [ ! -d /proc/$pid ] || { [ -f "$fc/results.jsonl" ] && [ "$(wc -l < "$fc/results.jsonl")" -ge 500 ]; }; do sleep 30; done
    sleep 5
    uv run python scripts/forkcheck/compare.py "$fc" --baseline "$base" | tee "$fc/compare.txt" | tee -a "$OUT/queue.log"
  fi
  log "pass done $fc rows=$(wc -l < "$fc/results.jsonl")"
}

pass "$BASE" "$OLD"
[[ "${SINGLE:-0}" == "1" ]] || pass "$REP" "$BASE"
echo OK > "$OUT/DONE-$RUN"
log "chain done"
