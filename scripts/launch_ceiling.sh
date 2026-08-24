#!/bin/bash
# M9 ceiling measurement driver (pins: m9-plan.md "The ceiling measurement",
# 2026-08-24). Runs the 8 certify lanes (horizon-2 + game-end), concatenates
# lane outs, runs the pinned read, notifies, and unregisters from watchd.
set -u
ROOT=/home/tyrathalis/Everything/Projects/Anvil
DIR="$ROOT/data/census/run-20260824-ceiling"
cd "$DIR"

for l in ceilh2-lane-*.sh ceilend-lane-*.sh; do
  sh "$l" > "${l%.sh}.log" 2>&1 &
done
wait

cat "$DIR"/ceilh2-lane-*.out.jsonl > "$DIR/ceilh2.out.jsonl"
cat "$DIR"/ceilend-lane-*.out.jsonl > "$DIR/ceilend.out.jsonl"

cd "$ROOT"
python3 scripts/payment_ceiling.py read \
  --master "$DIR/ceiling-master.jsonl" \
  --h2 "$DIR/ceilh2.out.jsonl" \
  --end "$DIR/ceilend.out.jsonl" > "$DIR/read.log" 2>&1
STATUS=$?

python3 - "$STATUS" <<'EOF'
import json, sys
from anvil.training.notify import notify
status = sys.argv[1]
d = "/home/tyrathalis/Everything/Projects/Anvil/data/census/run-20260824-ceiling"
try:
    r = json.load(open(f"{d}/ceiling-read.json"))
    h = r["headline"]
    notify("ceiling read DONE",
           f"dWin {h['windiff']:+.4f} +/- {h['se']:.4f} (z {h['z']:+.2f}) "
           f"n={r['denominator']} recert {r['recert_rate']:.0%}")
except Exception as e:
    notify("ceiling read FAILED", f"exit {status}: {e} — see {d}/read.log")
EOF

python3 "$ROOT/scripts/anvil_watchd.py" unregister --name ceiling-20260824
