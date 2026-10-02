#!/usr/bin/env bash
# ADR-0119 rung 2 attribution (10-02, the running record's halt entry): the halted stopgrad cell's
# ITERATION-0 TRAINING replayed on its own store (same ckpt = day-zero, same seed, same flags) under
# six settings, ~11 min each, to tell the two candidate mechanisms apart before any 30-h rerun:
#   ctrl         no stop-grad, anchor 0.1 (= the anchor-w01 recipe on THIS store: the control on identical data)
#   sg           the cell as run (replay fidelity + the same-seed baseline)
#   sg-t3e6      stop-grad + --trunk-lr 3e-6        (mechanism 1: the optimizer's step on the trunk)
#   sg-t1e6      stop-grad + --trunk-lr 1e-6
#   sg-h1e4      stop-grad + --value-head-lr 1e-4   (mechanism 2: the detached head's bias)
#   sg-t3e6-h1e4 both
# Reads per arm (read.md): kl_mu and v0 by step quarter + final, pg / v / ent, the gn_* rows.
# Launch: uv run python -m anvil.runs launch --name rung2-attrib --dir data/runs/rung2-attrib \
#           --watch 'data/training/rung2-attrib-*' --stall-min 30 -- bash scripts/rung2_attrib_replay.sh
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/rung2-attrib; mkdir -p "$OUT"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
# the cell's iteration-0 command, minus --out and the switch (re-added per arm)
BASE=$(grep -m1 "anvil.training.rl" data/runs/settings-pass3/stopgrad.loop.log | sed 's/.*python3 //' \
  | sed 's/ --out data\/training\/settings-stopgrad\/iter-000\/train//; s/ --value-stopgrad-trunk//; s/ --log-every [0-9]*//')
[[ -n "$BASE" ]] || { log "no base command"; exit 1; }
log "base: $BASE"
declare -A EXTRA=(
  [ctrl]=""
  [sg]="--value-stopgrad-trunk"
  [sg-t3e6]="--value-stopgrad-trunk --trunk-lr 3e-6"
  [sg-t1e6]="--value-stopgrad-trunk --trunk-lr 1e-6"
  [sg-h1e4]="--value-stopgrad-trunk --value-head-lr 1e-4"
  [sg-t3e6-h1e4]="--value-stopgrad-trunk --trunk-lr 3e-6 --value-head-lr 1e-4"
)
for arm in ctrl sg sg-t3e6 sg-t1e6 sg-h1e4 sg-t3e6-h1e4; do
  O=data/training/rung2-attrib-$arm
  if [[ -f "$O/DONE" ]]; then log "arm $arm done already"; continue; fi
  rm -rf "$O"; log "arm $arm: ${EXTRA[$arm]}"
  nice -n 19 uv run python $BASE --out "$O" --log-every 5 ${EXTRA[$arm]} > "$OUT/$arm.log" 2>&1 || { log "arm $arm FAILED rc=$?"; exit 1; }
  log "arm $arm done: $(grep -m1 '\[rl\] done' $OUT/$arm.log)"
done
uv run python - <<'PY' | tee "$OUT/read.md"
import json, statistics as st
arms = ["ctrl", "sg", "sg-t3e6", "sg-t1e6", "sg-h1e4", "sg-t3e6-h1e4"]
print("# Rung 2 attribution replays (iteration 0 of the halted stopgrad cell, its own store, same seed)\n")
print("References, the cells' own iteration 0 (log-every 20): stopgrad kl_mu quarters 0.0004 / 0.0023 / 0.0083 / 0.0201, v0 end 0.59; anchor-w01 0.0001 / 0.0007 / 0.0016 / 0.0020, v0 end 0.46; alloc 0.0000 / 0.0005 / 0.0026 / 0.0025, v0 end 0.44.\n")
print("| arm | rows | kl_mu by quarter (median) | kl_mu last 10 rows | v0 by quarter | v0 last 10 | pg med | v med | gn_pg med | gn_v med | gn_anchor med |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for a in arms:
    try:
        rows = [json.loads(l) for l in open(f"data/training/rung2-attrib-{a}/metrics.jsonl")]
    except FileNotFoundError:
        print(f"| {a} | missing |"); continue
    n = len(rows)
    q = lambda k, i: st.median(r[k] for r in rows[i*n//4:(i+1)*n//4] if k in r)
    last = lambda k: st.median(r[k] for r in rows[-10:] if k in r)
    med = lambda k: st.median(r[k] for r in rows if k in r) if any(k in r for r in rows) else float("nan")
    print(f"| {a} | {n} | " + " / ".join(f"{q('kl_mu', i):.4f}" for i in range(4)) + f" | {last('kl_mu'):.4f} | "
          + " / ".join(f"{q('v0', i):.3f}" for i in range(4)) + f" | {last('v0'):.3f} | {med('pg'):.4f} | {med('v'):.3f} | {med('gn_pg'):.4f} | {med('gn_v'):.4f} | {med('gn_anchor'):.4f} |")
PY
log "rung2 attribution replays done"; echo OK > "$OUT/DONE"
