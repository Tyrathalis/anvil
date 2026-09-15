#!/usr/bin/env bash
# M12 Build 3 evening 5 acting smoke (ADR-0106 A): the search behavior policy
# with SURFACE ACTING — bridged self-play games on the e3 build (six surfaces +
# tuck served), every quiescent main-phase window of the active seat searched
# (rate 1, rolls 2), the first traced surface on the top-B paths expanded
# (-searchsurf 2), the acting rule on options AND on the answers of the kinds
# in -searchactkinds (bar 0.10, T 0.025). Reads: scripts/act_smoke_read.py —
# the answer-stage verdicts (ans.by), the mainline arms' outcomes (the
# surfaceAct census rows: act / miss:* / unfired), the forward-call multiplier.
# Usage: build3_act_smoke.sh [games=8] [rate=1] [kinds=mode] [bar=0.10]
#   env: OUT, PORT, CKPT (the e3 build), JAR (a snapshot jar), ROLLS (2), SURF (2), CAP (8)
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
FORGE=/home/tyrathalis/Everything/Projects/forge
# JAR env = a snapshot jar (the 09-08 e3 smoke: the unconditional assignment below
# overrode the env; the run was saved only by target/ still equalling the snapshot)
JAR=${JAR:-$(ls -t $FORGE/forge-gui-desktop/target/*jar-with-dependencies.jar | head -1)}
OUT=${OUT:-$REPO/data/runs/build3-act-smoke}
PORT=${PORT:-50074}
CKPT=${CKPT:-$REPO/data/training/m12-build3-e3/last.pt}
GAMES=${1:-8}; RATE=${2:-1}; KINDS=${3:-mode}; BAR=${4:-0.10}; ROLLS=${ROLLS:-2}; SURF=${SURF:-2}; CAP=${CAP:-8}
export PYTHONUNBUFFERED=1 DISPLAY=:0
export XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1)
mkdir -p "$OUT"
cd "$REPO"
log() { echo "$(date -Iseconds) $*"; }
log "jar $JAR"
uv run python -m anvil.bridge.server --mode model --ckpt "$CKPT" --port $PORT --pass-delta 0 \
  > "$OUT/server.log" 2>&1 &
SERVER=$!
for i in $(seq 1 300); do (echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null && break; sleep 2; done
(echo > /dev/tcp/127.0.0.1/$PORT) 2>/dev/null || { log "server never opened port"; kill $SERVER; exit 1; }
log "server up pid=$SERVER"
rm -f "$OUT/search.jsonl" "$OUT/games.jsonl" "$OUT/census.jsonl" "$OUT/obs.zst" "$OUT/obs.idx.jsonl"
t0=$(date +%s)
( cd "$FORGE/forge-gui" && nice -n 19 java -Xmx3g -jar "$JAR" anvil \
    -d "dc-863946.dck" "dc-864920.dck" -f Commander -n "$GAMES" -s 20260907 \
    -b grpc:localhost:$PORT -reask -pool cf2ca6ba -forkcommit "$(git -C $FORGE rev-parse HEAD)" \
    -search -searchrate "$RATE" -searchrolls "$ROLLS" -searchsurf "$SURF" -searchsurfcap "$CAP" \
    -searchact "$BAR" -searchtemp 0.025 -searchactkinds "$KINDS" \
    -labels "$OUT/search.jsonl" \
    -results "$OUT/games.jsonl" -census "$OUT/census.jsonl" -obs "$OUT/obs.zst" \
    > "$OUT/anvil.log" 2>&1 )
rc=$?; t1=$(date +%s)
log "anvil rc=$rc wall=$((t1-t0))s"
kill -TERM $SERVER 2>/dev/null; sleep 3; kill -KILL $SERVER 2>/dev/null
echo "{\"games\":$GAMES,\"rate\":$RATE,\"kinds\":\"$KINDS\",\"bar\":$BAR,\"rolls\":$ROLLS,\"surf\":$SURF,\"cap\":$CAP,\"rc\":$rc,\"wall_s\":$((t1-t0))}" > "$OUT/DONE"
