#!/usr/bin/env bash
# THE UNION TARGET MASK'S GATE CHAIN (ADR-0122, 10-04): the fork tip 5b54fbe6ef (TargetUnion: each priority
# option carries its legal-target union on the opts entry) gets, in order, (1) the ADR-0025 forkcheck — the
# field is recording-only, so the standing 500-seed trace-hash read against the 09-16 merge baseline must
# come back identical but for the standing seed 20260969; (2) THE AGREEMENT CORPUS — the go/no-go the user
# set 10-02: a fresh heuristic-labelled corpus on the mask jar (pool pairs, obs + census on, no seat
# bridged), ingested and run through `anvil.store validate`, whose ADR-0122 branch checks every
# heuristic-chosen target (the plan's root-chain refs: tgt + subs — the decoder's label space) against the
# chosen option's listed set. PRE-REGISTERED (running record 10-04): the bar is ZERO targets outside the
# mask among masked options; an attributable miss class (one restriction family) is handled by declaring
# that class unmasked in TargetUnion.unmaskable and re-reading once; a residual miss after that = the mask is
# not exact and the item drops to after the big run. Unmasked options ("tg":null) are counted by reason, not
# checked; a cast on an option the fork flagged unfit ("tz") is an error of the same rank. The corpus's
# games-per-hour is exploratory (the timing check proper is the paired read's wall against the cast-mask
# read's 43 min on the same seeds).
# Launch (from the bridge worktree, data/ linked): uv run python -m anvil.runs launch --name tgtmask-agree \
#   --dir data/runs/tgtmask-agree --launched-by '<ListAgents name> [<ref>]' --watch 'data/runs/tgtmask-agree-*' \
#   --watch 'data/forkcheck/run-20261004-tgtmask' --stall-min 60 -- bash scripts/tgtmask_agree_queue.sh
set -u
REPO=${REPO:-$(cd "$(dirname "$0")/.." && pwd)}; cd "$REPO"
OUT=$REPO/data/runs/tgtmask-agree; mkdir -p "$OUT"
JAR=${JAR:-$REPO/data/runs/tgtmask/forge-tgtmask.jar}
FC=${FC:-$REPO/data/forkcheck/run-20261004-tgtmask}
GAMES=${GAMES:-2000}; WORKERS=${WORKERS:-24}; SEEDBASE=${SEEDBASE:-20261004}
STORE=$REPO/data/trajectories/tgtmask-agree
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
[[ -f "$JAR" ]] || { log "no jar at $JAR"; exit 1; }

# (1) the forkcheck of the mask tip
if [[ ! -f "$FC/compare.txt" ]]; then
  log "forkcheck start jar=$JAR ($(cat "$REPO/data/runs/tgtmask/forge-tgtmask.commit" 2>/dev/null))"
  N_GAMES=500 SEED=20260703 JAR="$JAR" bash scripts/forkcheck/run_forkcheck.sh "$FC" | tee -a "$OUT/queue.log"
  pid=$(cat "$FC/run.pid")
  until [ ! -d /proc/$pid ] || { [ -f "$FC/results.jsonl" ] && [ "$(wc -l < "$FC/results.jsonl")" -ge 500 ]; }; do
    sleep 60; touch "$OUT/.waiting"
  done
  uv run python scripts/forkcheck/compare.py "$FC" | tee "$FC/compare.txt" | tee -a "$OUT/queue.log"
fi

# (2) the agreement corpus: heuristic vs heuristic, every seat unbridged, obs + census on
if [[ ! -f "$OUT/gen.done" ]]; then
  log "agreement corpus: $GAMES games, $WORKERS workers, pool pairs, seed base $SEEDBASE"
  nice -n 19 uv run python -m anvil.bridge.harness launch --pool --pool-format dc --format Commander \
    --games "$GAMES" --games-per-pair 5 --workers "$WORKERS" --bridge local-random --bridge-seats 2 \
    --census --obs --purpose tgtmask-agree --seed-base "$SEEDBASE" --jar "$JAR" >> "$OUT/gen.log" 2>&1 \
    || { log "generation FAILED"; exit 1; }
  ls -dt data/runs/tgtmask-agree-2* | head -1 > "$OUT/gen.done"
fi
RUN=$(cat "$OUT/gen.done"); log "corpus run dir $RUN"
if [[ ! -d "$STORE" ]]; then
  uv run python -m anvil.store ingest "$RUN" --dest "$STORE" --pool-version "$(cat data/pool/CURRENT)" \
    >> "$OUT/ingest.log" 2>&1 || { log "ingest FAILED"; exit 1; }
fi
# the agreement check (exit 1 = errors = the bar is not met; the summary names every outside target)
uv run python -m anvil.store validate "$STORE" > "$OUT/validate.txt" 2>&1; echo "validate exit=$?" >> "$OUT/validate.txt"
tail -n 30 "$OUT/validate.txt" | tee -a "$OUT/queue.log"
log "chain done"; echo OK > "$OUT/DONE"
