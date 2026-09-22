#!/usr/bin/env bash
# ADR-0116 (09-21): the corrected target head's read — e1a (the served build, legacy head through the
# corrected decode) vs the refit build, network alone, GAMES per seat vs the heuristic, 24 x 2 ->
# the paired diff + the player-target audit on both arms + the mainline veto census by class.
# Launch: uv run python -m anvil.runs launch --name tgtfix-read --dir data/runs/build3-surface-read-tgtfix \
#           --watch 'data/runs/tgtfix-*' -- bash scripts/tgtfix_read_chain.sh
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
GAMES=${GAMES:-300}; WORKERS=${WORKERS:-24}
JAR=${JAR:-$REPO/data/runs/build4-census/forge-census.jar}
NAME=tgtfix CKPT=data/training/m12-build4-e1a/last.pt CKPT_ALT=data/training/m12-build4-e1a-tgt/last.pt \
  GAMES="$GAMES" WORKERS="$WORKERS" SERVERS=0 PORT=50087 JAR="$JAR" ARMS="on alt" FORGE_ARGS="" \
  bash scripts/build3_surface_read.sh || { echo "read chain FAILED"; exit 1; }
RD=data/runs/build3-surface-read-tgtfix
for arm in on alt; do
  uv run python scripts/player_target_audit.py $(cat $RD/$arm.done | tr ',' ' ') --json "$RD/player-target-audit-$arm.json" > "$RD/player-target-audit-$arm.txt"
  uv run python scripts/arms_report.py --arm "$arm=$(cat $RD/$arm.done)" --out "$RD/arms-$arm.json" > /dev/null 2>&1
done
python3 - "$RD" <<'PY'
import json, sys
rd = sys.argv[1]
for arm in ("on", "alt"):
    a = json.load(open(f"{rd}/player-target-audit-{arm}.json")); r = json.load(open(f"{rd}/arms-{arm}.json"))
    ms = a["model_seat0"]["self"] + a["model_seat1"]["self"]; mn = a["model_seat0"]["player_targets"] + a["model_seat1"]["player_targets"]
    hs = a["heur_seat0"]["self"] + a["heur_seat1"]["self"]; hn = a["heur_seat0"]["player_targets"] + a["heur_seat1"]["player_targets"]
    arm_r = r["arms"][0] if isinstance(r.get("arms"), list) else list(r.values())[0]
    print(f"{arm}: model self-target {ms}/{mn} = {ms/max(mn,1):.3f} (heur {hs}/{hn} = {hs/max(hn,1):.3f}); "
          f"veto_rate {arm_r.get('veto_rate'):.4f} vetoes {arm_r.get('vetoes')}")
PY
echo OK > "$RD/DONE"
