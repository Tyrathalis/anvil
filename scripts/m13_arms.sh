#!/usr/bin/env bash
# M13 Build 3 (ADR-0135): the three arms. One self-play loop per arm, each from big-run/iter-405 on the pinned
# jar, each stopped by the loop's wall budget (--wall-hours; a pause does not spend it). The arms differ in the
# lines marked ARM below and in nothing else:
#   control   the recipe of record (scripts/recipe.sh RECIPE + the ADR-0119 rung-2 value recipe)
#   nosearch  no search in generation: no acting by it, no labels from it, no search-row terms in the trainer
#   soft      the control plus the soft-target term on the searched, un-acted windows (rl.py --soft-frac);
#             its weight is pinned from the dose ladder before the arm launches (SOFT_FRAC, no default)
# Usage (the arm and its hours are ARGUMENTS: `anvil.runs relaunch` re-runs the recorded command without the
# launch's environment):
#   uv run python -m anvil.runs launch --name m13-control --dir data/runs/m13-control --resume-on-gone \
#     --launched-by '<ListAgents name> [<ref>]' --watch data/training/m13-control --watch 'data/runs/m13-control-*' \
#     --stall-min 180 -- bash scripts/m13_arms.sh control 168
#   A third argument sets the soft arm's SOFT_FRAC; a fourth its SOFT_TEMP.
# A smoke overrides by environment: NAME GAMES ITERS ARMS_EVERY ARMS_GAMES PORT SEED DAYZERO=0.
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
ARM=${1:?arm: control | nosearch | soft}; HOURS=${2:-168}
SOFT_FRAC=${3:-${SOFT_FRAC:-}}; SOFT_TEMP=${4:-${SOFT_TEMP:-0.1}}
case "$ARM" in
  control)  SEED_DEFAULT=20261201; PORT_DEFAULT=50140 ;;
  nosearch) SEED_DEFAULT=20261202; PORT_DEFAULT=50144 ;;
  soft)     SEED_DEFAULT=20261203; PORT_DEFAULT=50148
            [[ -n "$SOFT_FRAC" ]] || { echo "soft arm: SOFT_FRAC is pinned from the dose ladder; pass it as the third argument"; exit 2; } ;;
  *) echo "unknown arm $ARM"; exit 2 ;;
esac
NAME=${NAME:-m13-$ARM}; OUT=$REPO/data/runs/$NAME; mkdir -p "$OUT"
START=data/training/big-run/iter-405/train/last.pt
JAR=${JAR:-data/runs/m13-build2/forge-b2-mcguard.jar}                 # fork pin 68168fb214
ABIL="--abilities data/embeddings/abil-cf2ca6ba-m13-qwen3"            # the merged jar's ability table
BANK=data/runs/m12-build1; RUN_BANK=data/runs/run-holdout-seg4
SEED=${SEED:-$SEED_DEFAULT}; PORT=${PORT:-$PORT_DEFAULT}
GAMES=${GAMES:-480}; ITERS=${ITERS:-5000}; ARMS_EVERY=${ARMS_EVERY:-5}; ARMS_GAMES=${ARMS_GAMES:-200}
RL_WORKERS=${RL_WORKERS:-12}
. "$REPO/scripts/recipe.sh"
export ANVIL_EXTRA_JVM_OPTS="-Danvil.crash.trace=true -XX:+UseParallelGC"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }

# ARM: the search half. The control and the soft arm generate under RECIPE; nosearch passes no recipe, so the
# loop runs its pre-wiring path (no -search on the workers, no --search in the trainer, no with-lookahead arm).
case "$ARM" in
  control)  ARM_FLAGS=(--search-recipe "$RECIPE" --search-alloc head --search-floor 0.1 --arms-lookahead on) ;;
  nosearch) ARM_FLAGS=() ;;
  soft)     ARM_FLAGS=(--search-recipe "$RECIPE" --search-alloc head --search-floor 0.1 --arms-lookahead on
                       --soft-frac "$SOFT_FRAC" --soft-temp "$SOFT_TEMP" --soft-carry-w) ;;
esac

# Day zero on the in-loop instrument (the control only, once): iter-405 on the in-loop arm's seeds and pairs,
# network alone. The plan's "control falls" kill condition compares the mid-point in-loop read with it.
if [[ "$ARM" == control && "${DAYZERO:-1}" == 1 && ! -f "$OUT/dayzero.done" ]]; then
  log "day zero: iter-405 on the in-loop arm's seeds ($ARMS_GAMES per seat)"
  nice -n 39 uv run python scripts/final_read.py --ckpt "$START" --name "$NAME-dayzero" --games "$ARMS_GAMES" \
    --seed-base 20260710 --workers 24 --port $((PORT + 2)) --servers 0 --jar "$JAR" --server-args "$ABIL" \
    --skip-ante --quiet >> "$OUT/dayzero.log" 2>&1 && touch "$OUT/dayzero.done" || log "day zero FAILED (the loop goes on; rerun by hand)"
fi

T_LOOP=$(date +%s)
while true; do
  log "arm $ARM: loop $NAME wall_hours=$HOURS rl_workers=$RL_WORKERS seed_base=$SEED port=$PORT"
  uv run python -m anvil.training.selfplay --name "$NAME" --ckpt "$START" --iterations "$ITERS" --wall-hours "$HOURS" \
    --games "$GAMES" --games-per-pair 2 --workers 24 --chunk 30 --port "$PORT" --seed-base "$SEED" \
    --temperature 1.0 --replay 4 --fresh-weight 1.0 --replay-weight 0.33 --rl-workers "$RL_WORKERS" --epochs 1 --lr 1e-5 \
    --ent-weight 0.003 --ent-floor 0.08 --rl-seg 128 --guard-kl 0.06 --guard-ent-mult 2.0 --guard-veto-mult 1.5 \
    --guard-casts-floor 0.8 --guard-alloc-share 0.10 --penalty 0.02 --heur-frac 0.5 --mc-frac 0.1 --value-weight 0.5 --traj-per-step 4 \
    --arms-every "$ARMS_EVERY" --arms-pairs data/runs/d5arm-d0-s0-20260714-143546/pairs.txt --arms-games "$ARMS_GAMES" --arms-seed-base 20260710 \
    --reask --jar "$JAR" --server-args "$ABIL" "${ARM_FLAGS[@]}" \
    --distill-carry-w --alloc-carry-w --state-bank "$BANK" --guard-spearman-floor "${SPEARMAN_FLOOR:-0.30}" \
    --state-bank-run "$RUN_BANK" --guard-spearman-run-floor 0 \
    --value-anchor "$BANK" --anchor-weight 0.1 --anchor-every 32 --guard-anchor-gap 0.15 \
    --value-stopgrad-trunk --trunk-lr 3e-6 --value-head-lr 1e-4 \
    --grad-norm-every 50 --train-mem-floor-gb "${MEM_FLOOR:-24}" >> "$OUT/loop.log" 2>&1
  rc=$?
  if [[ $rc -eq 75 ]]; then log "another loop holds data/training/$NAME/loop.lock; this copy exits and touched nothing"; exit 1; fi
  # the memory watchdog's retry (the big run's rule): a learner it terminated fails the loop; rerun with half the workers
  if [[ $rc -ne 0 && -f "$OUT/WATCHDOG-TRIP" && $(stat -c %Y "$OUT/WATCHDOG-TRIP") -ge $T_LOOP && $RL_WORKERS -gt 2 ]]; then
    RL_WORKERS=$((RL_WORKERS / 2)); log "the memory watchdog tripped; rerunning with --rl-workers $RL_WORKERS"; continue
  fi
  break
done
log "arm $ARM: loop exit rc=$rc"
exit $rc
