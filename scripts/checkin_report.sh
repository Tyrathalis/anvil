#!/usr/bin/env bash
# ADR-0107: the check-in's ONE read command — unacked alerts (JSON), every
# run's state, and the last 30 log lines of each run named by an unacked alert
# or in a gone/stalled state. One shell approval covers the whole read.
cd /home/tyrathalis/Everything/Projects/Anvil
echo "== alerts (unacked)"; uv run python -m anvil.runs alerts --unacked --json
echo "== runs"; uv run python -m anvil.runs status
uv run python - <<'PY'
import json, subprocess
from anvil import runs
seen = set()
for a in runs.read_alerts(unacked_only=True):
    r = runs.read_run(a["run"]) or {}
    if r.get("log") and r["log"] not in seen:
        seen.add(r["log"]); print(f"== log tail {a['run']}: {r['log']}")
        try: print(open(r["log"], errors="replace").read()[-6000:].strip().splitlines()[-30:] and "\n".join(open(r["log"], errors="replace").read()[-6000:].splitlines()[-30:]))
        except OSError as e: print(f"(unreadable: {e})")
PY
