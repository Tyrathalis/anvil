#!/usr/bin/env bash
# M12 Build 3 evening 4 (ADR-0105): the payment evening's chain — waits for the
# payment pool (build3_surface_labels.sh's DONE), reads it, cross-fits the pay
# head (pay_fit.py: 5 folds → read → build → the e4 ckpt), smokes the served
# head with the margin bar, then runs the paired read (build3_surface_read.sh:
# off = the pay tag withheld, on = served, rescue = served + -payrescue) on the
# snapshot jar. Resumable at every stage (a stage whose artifact exists is
# skipped). Detached-run checklist: setsid nohup by the caller; watchd +
# notify inside. Usage: build3_pay_chain.sh
#   env: POOL_OUT (data/runs/build3-surface-labels3), OUT (data/runs/build3-e4),
#        CKPT (the e3 ckpt), CKPT_OUT (data/training/m12-build3-e4), JAR (the
#        snapshot the read runs on), BAR (0.03), TEMP (0.025), MIN_ROLLS (2),
#        FOLDS (5), STEPS (3000), EPOCHS (6), PAY_BAR (the serve bar, 0.2 nats),
#        READ_GAMES (300), ARMS ("off on rescue"), PORT (50066), SMOKE_PORT (50079)
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil
FORGE=/home/tyrathalis/Everything/Projects/forge
cd "$REPO"
POOL_OUT=${POOL_OUT:-data/runs/build3-surface-labels3}
OUT=${OUT:-data/runs/build3-e4}
CKPT=${CKPT:-data/training/m12-build3-e3/last.pt}
CKPT_OUT=${CKPT_OUT:-data/training/m12-build3-e4}
JAR=${JAR:-$REPO/data/runs/build3-e4/forge-b3e4r.jar}
BAR=${BAR:-0.03}; TEMP=${TEMP:-0.025}; MIN_ROLLS=${MIN_ROLLS:-2}
FOLDS=${FOLDS:-5}; STEPS=${STEPS:-3000}; EPOCHS=${EPOCHS:-6}
PAY_BAR=${PAY_BAR:-0.2}
READ_GAMES=${READ_GAMES:-300}; ARMS=${ARMS:-off on rescue}; PORT=${PORT:-50066}; SMOKE_PORT=${SMOKE_PORT:-50079}
TAGS_NOPAY=mtg.priority,mtg.mulligan_keep,mtg.mulligan_tuck,mtg.trigger,mtg.binary,mtg.number,mtg.attack,mtg.block,mtg.surface.entity_one,mtg.surface.entity_set,mtg.surface.mode,mtg.surface.order,mtg.surface.damage
export PYTHONUNBUFFERED=1 DISPLAY=:0
export XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1)
mkdir -p "$OUT"
LOG="$OUT/paychain.log"
log() { echo "$(date -Iseconds) $*" | tee -a "$LOG"; }
state() { echo "{\"stage\":\"$1\",\"at\":\"$(date -Iseconds)\"}" >> "$OUT/paychain-stages.jsonl"; }
python3 scripts/anvil_watchd.py register --name build3-paychain --pid $$ --dir "$REPO/$OUT" --stall-min 120
notify() { python3 -c "from anvil.training.notify import notify; notify('$1', '$2', tag='build3')"; }
finish() { python3 scripts/anvil_watchd.py unregister --name build3-paychain; if [[ $1 -eq 0 ]]; then notify "anvil build3 pay chain DONE" "$OUT/read.md + data/runs/build3-surface-read-b3e4/read.json"; else notify "anvil build3 pay chain FAILED" "rc=$1 see $LOG"; fi; exit $1; }
log "chain start pool=$POOL_OUT out=$OUT ckpt=$CKPT jar=$JAR bar=$BAR T=$TEMP rolls>=$MIN_ROLLS folds=$FOLDS steps=$STEPS paybar=$PAY_BAR arms='$ARMS'"

# ---- 1. wait for the pool
state wait-pool
while [[ ! -f "$POOL_OUT/DONE" ]]; do
  sleep 120
  # a heartbeat so the watchd stall clock reads the wait as alive (the pool is
  # the artifact producer here, not this chain)
  date -Iseconds > "$OUT/paychain-waiting"
done
RUN=$(python3 -c "import json; print(json.load(open('$POOL_OUT/DONE'))['run'])")
RC=$(python3 -c "import json; print(json.load(open('$POOL_OUT/DONE'))['rc'])")
log "pool landed rc=$RC run=$RUN"
[[ "$RC" == "0" ]] || log "pool rc=$RC — continuing on what landed"
[[ -d "$RUN" ]] || { log "pool run dir missing"; finish 1; }

# ---- 2. the pool read (sub rows / positives at the bar / the resolution-effect census)
if [[ ! -f "$OUT/pool-read.md" ]]; then
  state pool-read
  uv run python - "$RUN" "$BAR" "$TEMP" "$MIN_ROLLS" > "$OUT/pool-read.md" 2>> "$LOG" <<'EOF'
import sys, json, collections
from pathlib import Path
from anvil.training.pay_distill import pay_groups
run, bar, temp, rolls = Path(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])
c = collections.Counter(); margins = []; spreads = []; leaves = collections.Counter(); games = set()
for g in pay_groups(run, bar, temp, rolls, c):
    margins.append(g["margin"]); spreads.append(g["spread"]); leaves[g["leaf"]] += 1; games.add(g["seed"])
import numpy as np
m = np.array(margins) if margins else np.zeros(1)
print(f"# payment pool read: {run}\n")
print(f"games with pay sub rows {len(games)}; usable groups {len(margins)} ({len(margins)/max(1,len(games)):.1f}/game); leaf {dict(leaves)}")
print(f"counts {dict(c)}")
print(f"margin quantiles p50 {np.quantile(m,.5):.4f} p90 {np.quantile(m,.9):.4f} p97 {np.quantile(m,.97):.4f} p99 {np.quantile(m,.99):.4f} max {m.max():.4f}")
for b in (0.01, 0.02, 0.03, 0.05, 0.08):
    print(f"positives at bar {b}: {int((m >= b).sum())} ({(m >= b).mean():.3f})")
print()
EOF
  uv run python scripts/surface_served_census.py "$RUN" >> "$OUT/pool-read.md" 2>> "$LOG"
  log "pool read: $(grep -m2 'usable groups\|positives at bar 0.03' $OUT/pool-read.md | tr '\n' ' ')"
fi

# ---- 3. the cross-fit
for f in $(seq 0 $((FOLDS-1))); do
  if [[ -f "$OUT/payfit-result-fold$f.json" ]]; then log "fold $f done already"; continue; fi
  state "fold$f"
  nice -n 10 uv run python -m anvil.training.pay_fit --run "$RUN" --out "$OUT" --ckpt "$CKPT" --fold "$f" --folds "$FOLDS" \
      --bar "$BAR" --temp "$TEMP" --min-rolls "$MIN_ROLLS" --steps "$STEPS" --epochs "$EPOCHS" >> "$OUT/payfit-fold$f.log" 2>&1 || { log "fold $f FAILED"; finish 1; }
  log "fold $f: $(python3 -c "import json; r=json.load(open('$OUT/payfit-result-fold$f.json')); print('before', r['before'], 'after', r['after'])")"
done
uv run python -m anvil.training.pay_fit --run "$RUN" --out "$OUT" --read >> "$OUT/payfit-read.log" 2>&1 || { log "read FAILED"; finish 1; }
log "read: $(tail -3 $OUT/payfit-read.md | tr '\n' ' ')"

# ---- 4. the build
if [[ ! -f "$CKPT_OUT/last.pt" ]]; then
  state build
  nice -n 10 uv run python -m anvil.training.pay_fit --run "$RUN" --out "$OUT" --ckpt "$CKPT" --build --ckpt-out "$CKPT_OUT" --folds "$FOLDS" \
      --bar "$BAR" --temp "$TEMP" --min-rolls "$MIN_ROLLS" --steps "$STEPS" --epochs "$EPOCHS" >> "$OUT/payfit-build.log" 2>&1 || { log "build FAILED"; finish 1; }
fi
log "build: $CKPT_OUT/last.pt"

# ---- 5. the served-head smoke (8 bridged games, every tag incl. pay, the margin bar; no search)
SMOKE="$REPO/$OUT/pay-smoke"  # absolute: the java launch cds into forge-gui (the 09-09 rc=1)
if [[ ! -f "$SMOKE/DONE" || "$(cat "$SMOKE/DONE")" != "rc=0" ]]; then  # a failed smoke is not done (the 09-09 stale DONE skipped it)
  state smoke
  mkdir -p "$SMOKE"
  uv run python -m anvil.bridge.server --mode model --ckpt "$CKPT_OUT/last.pt" --port $SMOKE_PORT --pass-delta 0 --pay-bar "$PAY_BAR" > "$SMOKE/server.log" 2>&1 &
  SERVER=$!
  for i in $(seq 1 300); do (echo > /dev/tcp/127.0.0.1/$SMOKE_PORT) 2>/dev/null && break; sleep 2; done
  ( cd "$FORGE/forge-gui" && nice -n 19 java -Xmx3g -jar "$JAR" anvil -d "dc-863946.dck" "dc-864920.dck" -f Commander -n 8 -s 20260908 \
      -b grpc:localhost:$SMOKE_PORT -reask -pool cf2ca6ba -results "$SMOKE/games.jsonl" -census "$SMOKE/census.jsonl" -obs "$SMOKE/obs.zst" > "$SMOKE/anvil.log" 2>&1 ); rc=$?
  kill -TERM $SERVER 2>/dev/null; sleep 3; kill -KILL $SERVER 2>/dev/null
  echo "rc=$rc" > "$SMOKE/DONE"
  uv run python scripts/surface_served_census.py "$SMOKE" "$SMOKE/server.log" > "$SMOKE/read.md" 2>&1
  log "smoke rc=$rc: $(grep -o '"status":"[a-zA-Z_:]*"' $SMOKE/games.jsonl | sort | uniq -c | tr '\n' ' '); $(grep -A3 'payment windows' $SMOKE/read.md | tr '\n' ' ')"
  [[ "$rc" == "0" ]] || { log "smoke rc=$rc — stopping before the read"; finish 1; }
fi

# ---- 6. the paired read (off = the pay tag withheld; on = served with the bar; rescue = + -payrescue)
state read
NAME=b3e4 CKPT="$CKPT_OUT/last.pt" GAMES="$READ_GAMES" PORT="$PORT" JAR="$JAR" TAGS_OFF="$TAGS_NOPAY" ARMS="$ARMS" SERVER_ARGS="--pay-bar $PAY_BAR" \
  bash scripts/build3_surface_read.sh >> "$OUT/read-chain.log" 2>&1 || { log "paired read FAILED"; finish 1; }
log "paired read: $(python3 -c "import json; r=json.load(open('data/runs/build3-surface-read-b3e4/read.json')); print(json.dumps(r.get('paired', r))[:700])")"
state done
finish 0
