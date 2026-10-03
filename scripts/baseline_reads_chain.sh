#!/usr/bin/env bash
# THE BASELINE READS (10-01, user): how strong are the model and the heuristic against uniform random,
# and how does Forge's own simulation AI compare with the heuristic under our search, strength and cost.
# Exploratory (no pre-registered bar); every arm runs on ONE jar on a quiet box at one worker count, the
# test seat in both seat positions, the other seat Forge's heuristic unless named:
#   randheur    uniform random vs the heuristic                    (-randomseats {seat})
#   modelrand   the model, network alone, vs uniform random         (-randomseats {other})
#   heur        the heuristic mirror: 0.5 by symmetry; the cost unit
#   heursearch  the heuristic + our search, network leaf            (the Build 2 control string; +2.51 ± 1.00pp
#               at 1.27x wall on the 09-07 jar, ADR-0104 addendum)
#   probes      small fixed-size cost probes, each under a wall timeout: the heuristic + Forge's full and
#               hybrid simulation (-aisim full|hybrid -aisimseats {seat}), and the heuristic + our search with
#               the network-free leaf (-searchleaf end: every candidate played to game end by the heuristic)
# Random = FullRandomBridge (fork branch baseline-reads, 7ac02da6a9): uniform over every bridged decision,
# combat and targets included; the engine pays mana and orders combat damage (Spellbench's defaults).
# The jar is built from ../forge-baselines (the research master + the two default-off flags); its numbers
# compare with each other, not with the record's reads. The probes size the sim / end-leaf strength arms,
# which are a second launch. Results: data/runs/baseline-reads/read.md.
# Launch (from the main checkout, AFTER settings-pass3 closes and this branch is merged):
#   uv run python -m anvil.runs launch --name baseline-reads --dir data/runs/baseline-reads \
#     --watch 'data/runs/br-*' --stall-min 90 -- bash scripts/baseline_reads_chain.sh
#   env: WORKERS (24), N_RAND (200 / seat), N_SEARCH (1000 / seat), N_PROBE (24 / seat), PROBE_HOURS (3)
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
FORK=/home/tyrathalis/Everything/Projects/forge-baselines
OUT=$REPO/data/runs/baseline-reads; mkdir -p "$OUT"
WORKERS=${WORKERS:-24}; N_RAND=${N_RAND:-200}; N_SEARCH=${N_SEARCH:-1000}; N_PROBE=${N_PROBE:-24}
PROBE_HOURS=${PROBE_HOURS:-3}; SEED_BASE=${SEED_BASE:-20261002}
CKPT=data/training/shakedown-alloc/iter-019/train/last.pt
# -search needs -labels <file> (the fork FATALs without it); the search arms pass final_read --labels
SEARCH="-search -searchrate 1 -searchrolls 1 -searchact 0.05 -searchtemp 0.025"
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }

JAR=$OUT/forge-baselines.jar
if [[ ! -f "$JAR" ]]; then
  log "building the baseline jar from $FORK ($(git -C "$FORK" rev-parse --short HEAD))"
  (cd "$FORK" && nice -n 19 ~/.local/opt/maven/bin/mvn -q -P windows-linux -pl forge-gui-desktop -am package -DskipTests) \
    >> "$OUT/build.log" 2>&1 || { log "jar build FAILED"; exit 1; }
  cp "$(ls -t "$FORK"/forge-gui-desktop/target/*-jar-with-dependencies.jar | head -1)" "$JAR"
  echo "$(git -C "$FORK" rev-parse HEAD)" > "$OUT/jar.commit"
fi
log "baseline reads start jar=$JAR ($(cat "$OUT/jar.commit")) workers=$WORKERS seed_base=$SEED_BASE"

# arm name, games per seat, games per pair, timeout hours (0 = none), then final_read flags
run_arm() {
  local arm=$1 games=$2 gpp=$3 hours=$4; shift 4
  if [[ -f "$OUT/$arm.done" ]]; then log "arm $arm done already"; return 0; fi
  log "arm $arm: $games games / seat"
  local cmd=(nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT" --name "br-$arm" --games "$games"
    --games-per-pair "$gpp" --seed-base "$SEED_BASE" --workers "$WORKERS" --port 50090 --servers 0
    --jar "$JAR" --skip-ante "$@")
  if [[ "$hours" != 0 ]]; then
    timeout --signal=TERM "${hours}h" "${cmd[@]}" >> "$OUT/$arm.log" 2>&1
    log "arm $arm exit $? (a probe: a timeout keeps the games already written)"
    # a timed-out final_read leaves its server, harness and worker jars (no stop verb; kill each)
    pkill -TERM -f -- "--port 50090" 2>/dev/null; pkill -TERM -f -- "--purpose br-${arm}arm" 2>/dev/null
    pkill -TERM -f -- "$JAR" 2>/dev/null; sleep 10
  else
    "${cmd[@]}" >> "$OUT/$arm.log" 2>&1 || { log "arm $arm FAILED"; exit 1; }
  fi
  local s0 s1
  s0=$(ls -dt data/runs/br-${arm}arm-s0-* 2>/dev/null | head -1); s1=$(ls -dt data/runs/br-${arm}arm-s1-* 2>/dev/null | head -1)
  echo "$s0,$s1" > "$OUT/$arm.done"
  log "arm $arm closed: $s0 $s1"
}

run_arm randheur   "$N_RAND"   1 0 --heuristic-control --seat-forge-args "-randomseats {seat}"
run_arm modelrand  "$N_RAND"   1 0 --seat-forge-args "-randomseats {other}"
run_arm heur       "$N_RAND"   1 0 --heuristic-control
run_arm heursearch "$N_SEARCH" 5 0 --heuristic-control --forge-args "$SEARCH" --labels
run_arm simfull    "$N_PROBE"  1 "$PROBE_HOURS" --heuristic-control --seat-forge-args "-aisim full -aisimseats {seat}"
run_arm simhybrid  "$N_PROBE"  1 "$PROBE_HOURS" --heuristic-control --seat-forge-args "-aisim hybrid -aisimseats {seat}"
run_arm searchend  "$N_PROBE"  1 "$PROBE_HOURS" --heuristic-control --forge-args "$SEARCH -searchleaf end" --labels

args=()
for arm in heur randheur modelrand heursearch simfull simhybrid searchend; do
  [[ -f "$OUT/$arm.done" ]] && args+=(--arm "$arm=$(cat "$OUT/$arm.done")")
done
{
  printf '# The baseline reads (10-01 plan) — strength vs random, simulation vs search\n\n'
  printf 'Jar %s (fork %s); ckpt %s; %s workers; seed base %s. Exploratory: no pre-registered bar.\n' \
    "$JAR" "$(cat "$OUT/jar.commit")" "$CKPT" "$WORKERS" "$SEED_BASE"
  printf 'Test-seat win rate in both seat positions; the opponent is the heuristic except modelrand (random).\n'
  printf 'Cost: game ms per priority window, x the heuristic mirror. Probes (sim*, searchend) are cost reads, n small.\n\n'
  uv run python scripts/baseline_reads.py "${args[@]}" --ref heur --out "$OUT/reads.json"
} > "$OUT/read.md" 2>&1
log "baseline reads chain done: $(tail -n +7 "$OUT/read.md" | tr '\n' ' ')"; echo OK > "$OUT/DONE"
