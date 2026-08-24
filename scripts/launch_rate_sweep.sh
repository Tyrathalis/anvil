#!/bin/bash
# M9 window-rate sweep chain (ADR-0073 decision 4; pins in the m9-plan
# addendum, 2026-08-24): fresh in-era census -> mine (tag universe) ->
# uniform 600-window sample -> h2 certification -> rate read. Each stage
# guards; any failure notifies and stops.
set -u
ROOT=/home/tyrathalis/Everything/Projects/Anvil
DIR="$ROOT/data/census/run-20260824-ratesweep"
JAR=/home/tyrathalis/Everything/Projects/forge/forge-gui-desktop/target/forge-gui-desktop-2.0.15-SNAPSHOT-jar-with-dependencies.jar

fail() {
  python3 -c "from anvil.training.notify import notify; import sys; notify('rate sweep FAILED', sys.argv[1])" "$1"
  python3 "$ROOT/scripts/anvil_watchd.py" unregister --name ratesweep-20260824
  exit 1
}

cd "$DIR"
for l in lane-*.sh; do sh "$l" > "${l%.sh}.log" 2>&1 & done
wait
N_PAIRS=$(ls pair-*.jsonl 2>/dev/null | wc -l)
[ "$N_PAIRS" -ge 95 ] || fail "census produced only $N_PAIRS/100 pairs"

cd "$ROOT"
python3 scripts/payment_drill_mine.py "$DIR"/pair-*.jsonl \
  --out "$DIR/drill-candidates.jsonl" > "$DIR/mine.log" 2>&1 \
  || fail "miner failed — see $DIR/mine.log"

python3 scripts/payment_rate_sweep.py sample \
  --candidates "$DIR/drill-candidates.jsonl" \
  --out "$DIR/sweep-jobs.jsonl" --n 600 --rng 20260824 \
  > "$DIR/sample.log" 2>&1 || fail "sampler failed — see $DIR/sample.log"

python3 scripts/payment_certify.py lanes --jobs "$DIR/sweep-jobs.jsonl" \
  --jar "$JAR" -n 4 >> "$DIR/sample.log" 2>&1 || fail "lane gen failed"
cd "$DIR"
for l in sweep-lane-*.sh; do sh "$l" > "${l%.sh}.log" 2>&1 & done
wait
cat "$DIR"/sweep-lane-*.out.jsonl > "$DIR/sweep.out.jsonl"
[ -s "$DIR/sweep.out.jsonl" ] || fail "certification produced no rows"

cd "$ROOT"
python3 scripts/payment_certify.py read --jobs "$DIR/sweep-jobs.jsonl" \
  --certout "$DIR/sweep.out.jsonl" --out "$DIR/sweep-certified.jsonl" \
  > "$DIR/read.log" 2>&1 || fail "certify read failed — see $DIR/read.log"

python3 scripts/payment_rate_sweep.py rate --frame "$DIR/frame.json" \
  --certified "$DIR/sweep-certified.jsonl" --out "$DIR/rate-read.json" \
  >> "$DIR/read.log" 2>&1 || fail "rate read failed — see $DIR/read.log"

python3 - <<'EOF'
import json
from anvil.training.notify import notify
d = "/home/tyrathalis/Everything/Projects/Anvil/data/census/run-20260824-ratesweep"
r = json.load(open(f"{d}/rate-read.json"))
p, lo, hi = r["rate"]
up = r["arithmetic"][1]
notify("rate sweep DONE",
       f"rate {r['positives']}/{r['sampled']} = {p:.3f} [{lo:.3f},{hi:.3f}]; "
       f"upper perfect-play {up['pp_per_game']:+.2f}pp/g -> {up['vs_gate_floor']} the floor")
EOF

python3 "$ROOT/scripts/anvil_watchd.py" unregister --name ratesweep-20260824
