#!/usr/bin/env bash
# Fork-fidelity measurement run (ADR-0001 M0 deliverable (b)): fork games via
# GameCopier at a random mid-game turn, replay with cloned RNG, diff trajectories.
#
# Usage: run_forkcheck.sh [out_dir]
#   env overrides: N_GAMES (default 500), SEED (default 20260703), HEAP (default 2g),
#                  FORGE_DIR (default ~/Everything/Projects/forge),
#                  EXTRA_ARGS (e.g. "-freshrng" or "-perturb"),
#                  FIXED_HASH=1 (deterministic identity hashCodes)
#
# FIXED_HASH=1 pins -XX:hashCode=3 (identity hash = a per-thread deterministic
# sequence instead of a per-JVM-launch random). Hash-ordered iteration in
# decision paths is our documented twin-nondeterminism residual; with this on,
# that class stops being probabilistic and becomes reproducible across JVMs, so
# a twin/bridge run isolates it from every other divergence source. Technique
# from liamiak's upstream #11360 diagnosis (2026-07-24). Diagnostic only —
# never pin it for corpus generation: it changes the very ordering we want to
# measure under production conditions.
#
# Detached via nohup — survives the launching terminal. Stop with:
#   kill "$(cat <out_dir>/run.pid)"
set -euo pipefail

FORGE_DIR="${FORGE_DIR:-$HOME/Everything/Projects/forge}"
FORGE_GUI_DIR="$FORGE_DIR/forge-gui"
JAR="$(ls "$FORGE_DIR"/forge-gui-desktop/target/forge-gui-desktop-*-jar-with-dependencies.jar | head -1)"
OUT_DIR="${1:-$HOME/Everything/Projects/Anvil/data/forkcheck/run-$(date +%Y%m%d-%H%M%S)}"
N_GAMES="${N_GAMES:-500}"
SEED="${SEED:-20260703}"
HEAP="${HEAP:-2g}"
DECK1="${DECK1:-Abzan Armor [TDC] [2025].dck}"
DECK2="${DECK2:-Arcane Maelstrom [C20] [2020].dck}"
HASH_ARGS=()
if [[ "${FIXED_HASH:-0}" == "1" ]]; then
  HASH_ARGS=(-XX:+UnlockExperimentalVMOptions -XX:hashCode=3)
fi

mkdir -p "$OUT_DIR"

# Provenance (design invariant: engine hash on everything)
{
  echo "date=$(date -Iseconds)"
  echo "engine_commit=$(git -C "$FORGE_DIR" rev-parse HEAD)"
  echo "engine_dirty=$(git -C "$FORGE_DIR" status --porcelain | wc -l)"
  echo "jar=$JAR"
  echo "n_games=$N_GAMES seed=$SEED heap=$HEAP extra_args=${EXTRA_ARGS:-}"
  echo "fixed_hash=${FIXED_HASH:-0}"
  echo "deck1=$DECK1"
  echo "deck2=$DECK2"
  java -version 2>&1 | head -1
} > "$OUT_DIR/meta.txt"

# Low priority: the desktop stays responsive; an idle box measures the same.
cd "$FORGE_GUI_DIR"
nohup nice -n 19 java -Xms"$HEAP" -Xmx"$HEAP" "${HASH_ARGS[@]}" \
  -jar "$JAR" forkcheck -d "$DECK1" "$DECK2" -f Commander \
  -n "$N_GAMES" -s "$SEED" -o "$OUT_DIR/results.jsonl" ${EXTRA_ARGS:-} \
  > "$OUT_DIR/run.log" 2>&1 &
RUN_PID=$!
echo "$RUN_PID" > "$OUT_DIR/run.pid"

echo "forkcheck started: pid=$RUN_PID out=$OUT_DIR"
