#!/usr/bin/env bash
# THE MONTE CARLO READS (M13 Build 0 step 3; m13-plan.md, ADR-0129): upstream's Flat Monte Carlo in a
# heuristic seat, no model and no GPU. Three stages, each idempotent on relaunch (the DONE markers):
#   clock   the calibration's reference: the desktop mode on its wall clock, both seats, ONE JVM on an idle
#           box (launch with --quiet-box). What an idle desktop achieves per decision.
#   ladder  the count budget at a ladder of round counts on the same seeds, one JVM per rung, side by side
#           (a count-budgeted game does not read the clock). Two more rungs check the instrument: the desktop
#           counts through the max flag and through profile properties must give the same games.
#   read    Monte Carlo on against off at the calibrated counts (ROUNDS), both seat assignments, plus the
#           plain mirror on the same seeds and the desktop mode on its clock under the fleet's load.
#   ckpt    step 4: a checkpoint, network alone, against the Monte Carlo heuristic at ROUNDS, on the era
#           bridge's seeds, paired with the same checkpoint's plain-heuristic arms (PLAIN_ARMS, on file).
# Report: uv run python scripts/m13_mc_report.py <stage> ...
# Launch:
#   uv run python -m anvil.runs launch --name m13-mc-<stage> --dir data/runs/m13-mc/<stage> \
#     --launched-by '<ListAgents name> [<ref>]' [--quiet-box] [--watch 'data/runs/mc-*'] -- bash scripts/m13_mc.sh <stage>
#   env: JAR, PAIRS, SEED_CAL, CAL_GAMES, RUNGS, ROUNDS, SEED_READ, GAMES (per seat), CLOCK_GAMES (per seat), WORKERS
set -u
STAGE=${1:?stage: clock | ladder | read | ckpt}
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
FORGE_DIR=${FORGE_DIR:-/home/tyrathalis/Everything/Projects/forge}
JAR=${JAR:-$REPO/data/runs/m13-mc/forge-m13-mc-switch.jar}
COMMIT=$(cat "${JAR%.jar}.commit")
PAIRS=${PAIRS:-$REPO/data/runs/eb-newarm-s0-20261118-184910/pairs.txt}
SEED_CAL=${SEED_CAL:-20261119}; CAL_GAMES=${CAL_GAMES:-40}; RUNGS=${RUNGS:-"2 3 4 5 6 8 10"}
SEED_READ=${SEED_READ:-20261120}; GAMES=${GAMES:-2500}; CLOCK_GAMES=${CLOCK_GAMES:-500}; WORKERS=${WORKERS:-24}
OUT=${OUT_DIR:-$REPO/data/runs/m13-mc/$STAGE}; mkdir -p "$OUT"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }

# What the max flag sets beyond the four drawn profiles, as profile properties, so the counts can go BELOW
# the desktop's (Config.maximized() only raises). The ladder's two instrument rungs prove the equivalence.
DESKTOP="FLAT_MC_MAX_CANDIDATES=8,FLAT_MC_EXTRA_CANDIDATES=5,FLAT_MC_TARGET_VARIANTS=3,FLAT_MC_MAX_PLAYOUT_PLAYS=10"
DESKTOP+=",FLAT_MC_COMBO_PLAYOUT_PLAYS=20,FLAT_MC_OPPONENT_LOOKAHEAD=50,FLAT_MC_ATTACK=true,FLAT_MC_BROAD_DISCOVERY=true"
DESKTOP+=",FLAT_MC_PRUNING=true,FLAT_MC_CATEGORY_HOLD=true,FLAT_MC_ADAPTIVE_PLAYOUT=true,FLAT_MC_CONSIDER_HOLDING=true"
DESKTOP+=",FLAT_MC_MULLIGAN=true"
# <rounds> -> the count-budget properties: the desktop's 8 base + 6 extra rounds, scaled (base at least 2).
count_props() {
  local r=$1 base=$(( ($1 * 8 + 13) / 14 )); (( base < 2 )) && base=2; (( base > r )) && base=$r
  echo "$DESKTOP,FLAT_MC_COUNT_BUDGET=true,FLAT_MC_ROLLOUTS_PER_CANDIDATE=$base,FLAT_MC_EXTRA_ROUNDS=$(( r - base ))"
}

# One JVM, heuristic seats only, a desktop's heap and all its cores: <tag> <games> <AnvilRun flags...>
cell() {
  local tag=$1 games=$2; shift 2; local d=$OUT/$tag
  [[ -f "$d/DONE" ]] && return 0
  rm -rf "$d"; mkdir -p "$d"
  echo "$*" > "$d/args.txt"
  local t0=$SECONDS
  ( cd "$FORGE_DIR/forge-gui" && java -Xms4g -Xmx4g -XX:+ExitOnOutOfMemoryError -Danvil.crash.trace=true -jar "$JAR" anvil \
      -pairs "$PAIRS" -gpp 1 -f Commander -range 0 "$games" -seedbase "$SEED_CAL" -results "$d/games.jsonl" \
      -b local-random -bridgeseats 2 -pool cf2ca6ba -forkcommit "$COMMIT" "$@" > "$d/out.log" 2>&1 ) \
    || { log "cell $tag FAILED (rc $?)"; return 1; }
  [[ $(wc -l < "$d/games.jsonl") -eq $games ]] || { log "cell $tag is short: $(wc -l < "$d/games.jsonl") of $games"; return 1; }
  echo $(( SECONDS - t0 )) > "$d/DONE"; log "cell $tag done in $(( SECONDS - t0 )) s"
}

# One fleet arm through the harness: <purpose> <games> <AnvilRun flags or ''>  -> $OUT/<purpose>.done (the run dir)
arm() {
  local purpose=$1 games=$2 fargs=$3
  [[ -f "$OUT/$purpose.done" ]] && return 0
  log "arm $purpose: games=$games workers=$WORKERS forge-args='$fargs'"
  uv run python -m anvil.bridge.harness launch --pairs-file "$PAIRS" --format Commander --games "$games" \
    --games-per-pair 5 --workers "$WORKERS" --bridge local-random --bridge-seats 2 --purpose "$purpose" \
    --seed-base "$SEED_READ" --pool-version cf2ca6ba --jar "$JAR" \
    ${fargs:+"--forge-args=$fargs"} >> "$OUT/$purpose.log" 2>&1 || { log "arm $purpose FAILED"; return 1; }
  ls -dt "data/runs/$purpose-"* | head -1 > "$OUT/$purpose.done"
}

case "$STAGE" in
  clock)
    log "clock: desktop mode on its wall clock, both seats, one JVM, $CAL_GAMES games, seeds $SEED_CAL, load $(cut -d' ' -f1-3 /proc/loadavg)"
    cell clock "$CAL_GAMES" -mc max -mcseats 0,1 -mcdecisions || exit 1
    log "load at the end: $(cut -d' ' -f1-3 /proc/loadavg)"
    ;;
  ladder)
    log "ladder: count budget at rounds {$RUNGS} + the two instrument rungs, $CAL_GAMES games each, seeds $SEED_CAL"
    pids=()
    cell max-flag "$CAL_GAMES" -mc max -mcseats 0,1 -mcdecisions -mcprops FLAT_MC_COUNT_BUDGET=true & pids+=($!)
    cell max-props "$CAL_GAMES" -mc on -mcseats 0,1 -mcdecisions -mcprops "$(count_props 14)" & pids+=($!)
    for r in $RUNGS; do
      cell "r$r" "$CAL_GAMES" -mc on -mcseats 0,1 -mcdecisions -mcprops "$(count_props "$r")" & pids+=($!)
    done
    rc=0; for p in "${pids[@]}"; do wait "$p" || rc=1; done; (( rc == 0 )) || exit 1
    ;;
  read)
    ROUNDS=${ROUNDS:?the calibrated round count, from the ladder}
    P=$(count_props "$ROUNDS")
    log "read: Monte Carlo at $ROUNDS rounds against the plain heuristic, $GAMES / seat, seeds $SEED_READ, $WORKERS workers"
    arm mc-plain "$GAMES" "" || exit 1
    arm mc-count-s0 "$GAMES" "-mc on -mcseats 0 -mcdecisions -mcprops $P" || exit 1
    arm mc-count-s1 "$GAMES" "-mc on -mcseats 1 -mcdecisions -mcprops $P" || exit 1
    # the same arms' first CLOCK_GAMES seeds with the desktop mode on its clock: what the fleet's load does to it
    arm mc-clock-s0 "$CLOCK_GAMES" "-mc max -mcseats 0 -mcdecisions" || exit 1
    arm mc-clock-s1 "$CLOCK_GAMES" "-mc max -mcseats 1 -mcdecisions" || exit 1
    uv run python scripts/m13_mc_report.py read --out "$OUT" 2>&1 | tee "$OUT/read.md" | tee -a "$OUT/queue.log"
    ;;
  ckpt)
    ROUNDS=${ROUNDS:?the calibrated round count}
    CKPT=${CKPT:-data/training/big-run/iter-405/train/last.pt}; ABIL=${ABIL:-data/embeddings/abil-cf2ca6ba-m13-qwen3}
    SEED_CKPT=${SEED_CKPT:-20261107}; TAG=${TAG:-mcck}
    PLAIN_ARMS=${PLAIN_ARMS:-data/runs/eb-newarm-s0-20261118-184910,data/runs/eb-newarm-s1-20261118-192149}
    # the heuristic seat is the Monte Carlo seat (-mcseats defaults to the seats outside -bridgeseats);
    # a count-budget rollout can outgrow the fleet's 2g heap, so the cap is raised (the last -Xmx wins)
    export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true -Xmx${HEAP:-3g}}"
    if [[ ! -f "$OUT/$TAG.done" ]]; then
      log "ckpt: $CKPT against Monte Carlo at $ROUNDS rounds, $GAMES / seat, seeds $SEED_CKPT, $WORKERS workers, jvm '$ANVIL_EXTRA_JVM_OPTS'"
      nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT" --name "$TAG" --games "$GAMES" --games-per-pair 5 \
        --seed-base "$SEED_CKPT" --workers "$WORKERS" --port 50086 --servers 0 --jar "$JAR" --skip-ante \
        --server-args "--abilities $ABIL" --forge-args "-mc on -mcdecisions -mcprops $(count_props "$ROUNDS")" \
        >> "$OUT/$TAG.log" 2>&1 || { log "ckpt read FAILED"; exit 1; }
      echo "$(ls -dt "data/runs/${TAG}arm-s0-"* | head -1),$(ls -dt "data/runs/${TAG}arm-s1-"* | head -1)" > "$OUT/$TAG.done"
    fi
    A=$(cat "$OUT/$TAG.done")
    {
      echo "# $CKPT against the Monte Carlo heuristic ($ROUNDS rounds): seeds $SEED_CKPT, $GAMES / seat, network alone"
      echo
      echo "- against Monte Carlo: $(uv run python scripts/arms_report.py --arm "mc=$A" --out "$OUT/$TAG.json" 2>/dev/null | grep -o "winrate [0-9.]* ± [0-9.]*" | head -1)"
      echo "- against the plain heuristic (on file): $(uv run python scripts/arms_report.py --arm "plain=$PLAIN_ARMS" --out "$OUT/$TAG-plain.json" 2>/dev/null | grep -o "winrate [0-9.]* ± [0-9.]*" | head -1)"
      echo "- paired on seed, Monte Carlo minus plain: $(uv run python scripts/paired_arms.py --a "$A" --b "$PLAIN_ARMS" 2>&1 | tee "$OUT/$TAG.paired.txt" | grep -o 'A - B: [^)]*)' | head -1)"
      echo
      uv run python scripts/m13_mc_report.py arms --runs "$A" --rounds "$ROUNDS"
    } > "$OUT/$TAG.md" 2>&1 || { log "ckpt report FAILED"; exit 1; }
    cat "$OUT/$TAG.md" | tee -a "$OUT/queue.log"
    ;;
  *) echo "unknown stage $STAGE" >&2; exit 2 ;;
esac
log "$STAGE done"; echo OK > "$OUT/DONE"
