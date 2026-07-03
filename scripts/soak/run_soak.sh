#!/usr/bin/env bash
# Overnight soak test (ADR-0001 M0 deliverable): sustained headless self-play
# in a single JVM, watching RSS + GC to answer the LearnForge-leak question.
#
# Usage: run_soak.sh [out_dir]
#   env overrides: N_GAMES (default 10000), HEAP (default 4g),
#                  FORGE_DIR (default ~/Everything/Projects/forge)
#
# Detached via nohup — survives the launching terminal. Stop with:
#   kill "$(cat <out_dir>/sim.pid)"
# Analyze with: python scripts/soak/analyze_soak.py <out_dir>
set -euo pipefail

FORGE_DIR="${FORGE_DIR:-$HOME/Everything/Projects/forge}"
FORGE_GUI_DIR="$FORGE_DIR/forge-gui"
JAR="$(ls "$FORGE_DIR"/forge-gui-desktop/target/forge-gui-desktop-*-jar-with-dependencies.jar | head -1)"
OUT_DIR="${1:-$HOME/Everything/Projects/Anvil/data/soak/run-$(date +%Y%m%d-%H%M%S)}"
N_GAMES="${N_GAMES:-10000}"
HEAP="${HEAP:-4g}"
DECK1="${DECK1:-Abzan Armor [TDC] [2025].dck}"
DECK2="${DECK2:-Arcane Maelstrom [C20] [2020].dck}"

mkdir -p "$OUT_DIR"

# Provenance (design invariant: engine hash on everything)
{
  echo "date=$(date -Iseconds)"
  echo "engine_commit=$(git -C "$FORGE_DIR" rev-parse HEAD)"
  echo "engine_dirty=$(git -C "$FORGE_DIR" status --porcelain | wc -l)"
  echo "jar=$JAR"
  echo "n_games=$N_GAMES heap=$HEAP"
  echo "deck1=$DECK1"
  echo "deck2=$DECK2"
  java -version 2>&1 | head -1
} > "$OUT_DIR/meta.txt"

# Fixed heap (-Xms=-Xmx): a true leak shows as climbing heap-after-GC or OOM,
# not as ambiguous RSS drift from lazy heap growth.
# Low priority: the desktop stays responsive; an idle box measures the same.
cd "$FORGE_GUI_DIR"
nohup nice -n 19 java -Xms"$HEAP" -Xmx"$HEAP" \
  -Xlog:gc*:file="$OUT_DIR/gc.log":time,uptime \
  -jar "$JAR" sim -d "$DECK1" "$DECK2" -f Commander -n "$N_GAMES" -q \
  > "$OUT_DIR/sim.log" 2>&1 &
SIM_PID=$!
echo "$SIM_PID" > "$OUT_DIR/sim.pid"

# RSS sampler: 30s cadence, timestamped CSV. Also timestamps game progress so
# games/hour is computable (sim.log lines are unstamped).
nohup bash -c '
  pid='"$SIM_PID"'; out="'"$OUT_DIR"'"
  while kill -0 "$pid" 2>/dev/null; do
    rss=$(awk "/VmRSS/{print \$2}" "/proc/$pid/status" 2>/dev/null) || true
    games=$(grep -c "^Game Result" "$out/sim.log" 2>/dev/null) || true
    [ -n "$rss" ] && echo "$(date +%s),$rss,${games:-0}" >> "$out/rss.csv"
    sleep 30
  done
  echo "$(date -Iseconds) sim process exited" >> "$out/meta.txt"
' > /dev/null 2>&1 &

echo "soak started: pid=$SIM_PID out=$OUT_DIR"
