#!/usr/bin/env bash
# THE REPLAY FIDELITY READ (M13 Build 1; m13-plan.md done-when 2): served games played with the answer tape
# on, then every one replayed from its tape with no server (scripts/tape_replay.py) and compared with the
# stored game record by record. Four cells, so each kind of game the arms will store is replayed:
#   na    the network alone against the plain heuristic
#   srch  the search recipe acting, against the plain heuristic
#   self  both seats served, sampled at temperature 1, the search recipe acting behind the allocation head
#         (generation's self-play)
#   mc    the network alone against the Monte Carlo heuristic at the count budget
# Idempotent on relaunch (the .done markers). The read: games replayed identically / games, per cell.
# Launch:
#   uv run python -m anvil.runs launch --name replay-fidelity --dir data/runs/replay-fidelity \
#     --launched-by '<ListAgents name> [<ref>]' --watch 'data/runs/rf-*' -- bash scripts/m13_replay_fidelity.sh
#   env: REPO (the checkout to run from), JAR (required), CKPT, ABIL, SEED_BASE, NA / SRCH / SELF / MC (games
#        per seat arm, 0 skips the cell), ROUNDS (the Monte Carlo round count), ALLOC (the allocation threshold; empty = every window searched), WORKERS, MC_HEAP
set -u
REPO=${REPO:-/home/tyrathalis/Everything/Projects/Anvil}; cd "$REPO"
. "$REPO/scripts/recipe.sh"
JAR=${JAR:?the jar under test}
CKPT=${CKPT:-data/training/big-run/iter-405/train/last.pt}
ABIL=${ABIL:-data/embeddings/abil-cf2ca6ba-m13-qwen3}
SEED_BASE=${SEED_BASE:-20261120}; WORKERS=${WORKERS:-12}; ROUNDS=${ROUNDS:-8}; MC_HEAP=${MC_HEAP:-3g}
NA=${NA:-100}; SRCH=${SRCH:-50}; SELF=${SELF:-50}; MC=${MC:-10}; ALLOC=${ALLOC-0.5}
OUT=${OUT:-$REPO/data/runs/replay-fidelity}; mkdir -p "$OUT"
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
mc_props() {
  local r=$1 base=$(( ($1 * 8 + 13) / 14 )); (( base < 2 )) && base=2; (( base > r )) && base=$r
  echo "FLAT_MC_MAX_CANDIDATES=8,FLAT_MC_EXTRA_CANDIDATES=5,FLAT_MC_TARGET_VARIANTS=3,FLAT_MC_MAX_PLAYOUT_PLAYS=10,FLAT_MC_COUNT_BUDGET=true,FLAT_MC_ROLLOUTS_PER_CANDIDATE=$base,FLAT_MC_EXTRA_ROUNDS=$(( r - base ))"
}
cell() { # <tag> <games per seat> <server args> <final_read args...>
  local tag=$1 games=$2 sargs=$3; shift 3
  (( games > 0 )) || return 0
  if [[ ! -f "$OUT/$tag.done" ]]; then
    log "cell $tag: $games / seat, $*"
    nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT" --name "rf-$tag" --games "$games" --games-per-pair 5 \
      --seed-base "$SEED_BASE" --workers "$WORKERS" --port 50096 --servers 0 --jar "$JAR" --skip-ante \
      --server-args "--abilities $ABIL $sargs" "$@" >> "$OUT/$tag.log" 2>&1 || { log "cell $tag FAILED"; return 1; }
    echo "$(ls -dt "data/runs/rf-${tag}arm-s0-"* | head -1) $(ls -dt "data/runs/rf-${tag}arm-s1-"* | head -1)" > "$OUT/$tag.done"
  fi
  local arm
  for arm in $(cat "$OUT/$tag.done"); do
    [[ -f "$OUT/replay-$(basename "$arm")/replay-report.json" ]] && continue
    log "replay $arm"
    nice -n 19 uv run python scripts/tape_replay.py "$arm" --games 1000000 --jar "$JAR" --out "$OUT/replay-$(basename "$arm")" \
      --keep-going >> "$OUT/$tag.replay.log" 2>&1 || { log "replay $arm FAILED"; return 1; }
  done
}
log "replay fidelity: jar=$JAR ckpt=$CKPT seeds=$SEED_BASE na=$NA srch=$SRCH self=$SELF mc=$MC workers=$WORKERS"
cell na "$NA" "" || exit 1
cell srch "$SRCH" "" --labels --forge-args "$RECIPE" || exit 1
# both seats served: a later -bridgeseats overrides the seat arm's own
cell self "$SELF" "--sample --temperature 1.0 --mu-out $OUT/self-mu.jsonl" --labels \
  --forge-args "$RECIPE ${ALLOC:+-searchalloc $ALLOC -searchfloor 0.1} -bridgeseats 0,1" || exit 1
ANVIL_EXTRA_JVM_OPTS="$ANVIL_EXTRA_JVM_OPTS -Xmx$MC_HEAP" WORKERS=$(( WORKERS < 8 ? WORKERS : 8 )) \
  cell mc "$MC" "" --forge-args "-mc on -mcprops $(mc_props "$ROUNDS")" || exit 1
uv run python - "$OUT" <<'EOF' | tee -a "$OUT/queue.log"
import glob, json, sys
out = sys.argv[1]
tot = same = near = 0
for f in sorted(glob.glob(out + "/replay-*/replay-report.json")):
    r = json.load(open(f))
    tot += r["games"]; same += r["identical"]; near += r["same_game"]
    bad = [i["i"] for i in r["items"] if i["verdict"] == "differs" or i["verdict"].startswith("not")]
    print(f"{f.split('/')[-2]}: {r['identical']} of {r['games']} identical, {r['same_game']} the same game with extra callback records"
          + (f"; differing games {bad}" if bad else "") + (f"; untaped {len(r['untaped'])}" if r["untaped"] else ""))
print(f"TOTAL: {same} of {tot} games replayed identically, {near} more as the same game, {tot - same - near} differ")
EOF
log "replay fidelity done"; echo OK > "$OUT/DONE"
