#!/usr/bin/env bash
# Multi-worker scaling curve (M0): same soak workload at 1/2/4/8/16 parallel
# JVM processes, watching games/hour/worker vs GC pressure. Separate processes,
# not threads — MageZero's throughput halving was shared-heap GC contention;
# per-process heaps sidestep it and this measures whether anything else bites
# (memory bandwidth, allocation stalls, scheduler).
#
# Usage: run_scaling.sh [out_dir]   (BLOCKING — run under nohup or a background task)
#   env overrides: GAMES_PER_WORKER (default 300), HEAP (default 2g),
#                  WORKER_COUNTS (default "1 2 4 8 16"),
#                  FORGE_DIR (default ~/Everything/Projects/forge),
#                  EXTRA_JVM_OPTS (e.g. "-XX:ActiveProcessorCount=2" to cap
#                  per-worker GC threads — by default each JVM sizes its GC
#                  pool as if it owned all 32 CPUs)
set -euo pipefail

FORGE_DIR="${FORGE_DIR:-$HOME/Everything/Projects/forge}"
FORGE_GUI_DIR="$FORGE_DIR/forge-gui"
JAR="$(ls "$FORGE_DIR"/forge-gui-desktop/target/forge-gui-desktop-*-jar-with-dependencies.jar | head -1)"
OUT_DIR="${1:-$HOME/Everything/Projects/Anvil/data/soak/scaling-$(date +%Y%m%d-%H%M%S)}"
GAMES_PER_WORKER="${GAMES_PER_WORKER:-300}"
HEAP="${HEAP:-2g}"
WORKER_COUNTS="${WORKER_COUNTS:-1 2 4 8 16}"
DECK1="${DECK1:-Abzan Armor [TDC] [2025].dck}"
DECK2="${DECK2:-Arcane Maelstrom [C20] [2020].dck}"

mkdir -p "$OUT_DIR"

{
  echo "date=$(date -Iseconds)"
  echo "engine_commit=$(git -C "$FORGE_DIR" rev-parse HEAD)"
  echo "engine_dirty=$(git -C "$FORGE_DIR" status --porcelain | wc -l)"
  echo "jar=$JAR"
  echo "games_per_worker=$GAMES_PER_WORKER heap=$HEAP worker_counts=$WORKER_COUNTS extra_jvm_opts=${EXTRA_JVM_OPTS:-}"
  echo "deck1=$DECK1"
  echo "deck2=$DECK2"
  nproc
  java -version 2>&1 | head -1
} > "$OUT_DIR/meta.txt"

echo "config,worker,start_epoch,end_epoch,games" > "$OUT_DIR/timing.csv"

cd "$FORGE_GUI_DIR"

for W in $WORKER_COUNTS; do
  CFG_DIR="$OUT_DIR/w$W"
  mkdir -p "$CFG_DIR"
  echo "$(date -Iseconds) config w=$W starting" >> "$OUT_DIR/progress.log"
  PIDS=()
  STARTS=()
  for ((i = 0; i < W; i++)); do
    WDIR="$CFG_DIR/worker$i"
    mkdir -p "$WDIR"
    STARTS[$i]=$(date +%s)
    # Low priority: desktop use preempts workers. If the box is touched mid-config,
    # that config's games/h dips — per-config timing.csv makes it visible.
    nice -n 19 java -Xms"$HEAP" -Xmx"$HEAP" ${EXTRA_JVM_OPTS:-} \
      -Xlog:gc*:file="$WDIR/gc.log":time,uptime \
      -jar "$JAR" sim -d "$DECK1" "$DECK2" -f Commander -n "$GAMES_PER_WORKER" -q \
      > "$WDIR/sim.log" 2>&1 &
    PIDS[$i]=$!
  done

  # RSS sampler across all workers of this config, 30s cadence
  (
    while :; do
      alive=0
      for ((i = 0; i < W; i++)); do
        pid=${PIDS[$i]}
        if kill -0 "$pid" 2>/dev/null; then
          alive=1
          rss=$(awk '/VmRSS/{print $2}' "/proc/$pid/status" 2>/dev/null || true)
          games=$(grep -c "^Game Result" "$CFG_DIR/worker$i/sim.log" 2>/dev/null || true)
          echo "$(date +%s),$i,${rss:-0},${games:-0}" >> "$CFG_DIR/rss.csv"
        fi
      done
      [ "$alive" = 0 ] && break
      sleep 30
    done
  ) &
  SAMPLER=$!

  for ((i = 0; i < W; i++)); do
    wait "${PIDS[$i]}" || true
    END=$(date +%s)
    GAMES=$(grep -c "^Game Result" "$CFG_DIR/worker$i/sim.log" 2>/dev/null || echo 0)
    echo "w$W,$i,${STARTS[$i]},$END,$GAMES" >> "$OUT_DIR/timing.csv"
  done
  wait "$SAMPLER" 2>/dev/null || true
  echo "$(date -Iseconds) config w=$W done" >> "$OUT_DIR/progress.log"
done

echo "$(date -Iseconds) scaling sweep complete" >> "$OUT_DIR/progress.log"
