#!/usr/bin/env bash
# THE MARGIN READ for a settings-pass cell (10-02): the cell's final checkpoint read fresh, network
# alone, raw, on the certmerge jar at the RESOLUTION READ's seed base (20261001, 2,500 games per seat,
# 13 games per pair), so it pairs game-for-game with the fresh alloc read of record
# (data/runs/resolution-read/alloc.read.done: 0.5394 +/- 0.0070) at no new alloc games; then
# paired_arms writes the paired difference and the FIXED margin (cell - alloc >= -1.0pp on the point
# estimate) is applied. The chain's own 2,000-game read (seed base 20260710) is a first look, not this.
#   env: ARM (the cell's arm name, e.g. stopgrad-t3e6), CKPT (default: the cell's loop_state.json ckpt),
#        REF_DONE (the alloc rr dirs), MARGIN_PP (-1.0), WORKERS (24)
# Launch: ARM=stopgrad-t3e6 uv run python -m anvil.runs launch --name rung2-margin-read \
#           --dir data/runs/rung2-margin-read --watch 'data/runs/rr-*' --stall-min 60 -- bash scripts/margin_read_chain.sh
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
ARM=${ARM:?the arm name}; LOOP=data/training/settings-$ARM
if [[ -z "${CKPT:-}" ]]; then CKPT=$(python3 -c "import json; print(json.load(open('$LOOP/loop_state.json'))['ckpt'])"); fi
OUT=${OUT:-$REPO/data/runs/rung2-margin-read}; mkdir -p "$OUT"
REF_DONE=${REF_DONE:-$REPO/data/runs/resolution-read/alloc.read.done}
JAR=${JAR:-$REPO/data/runs/certmerge/forge-certmerge.jar}
WORKERS=${WORKERS:-24}; READ_GAMES=${READ_GAMES:-2500}; GPP=${GPP:-13}; SEED_BASE=${SEED_BASE:-20261001}; MARGIN_PP=${MARGIN_PP:--1.0}
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
[[ -f "$REF_DONE" ]] || { log "no reference read dirs at $REF_DONE"; exit 1; }
log "margin read start arm=$ARM ckpt=$CKPT jar=$JAR games=${READ_GAMES}/seat gpp=$GPP seed_base=$SEED_BASE ref=$(cat $REF_DONE)"
if [[ ! -f "$OUT/$ARM.read.done" ]]; then
  nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT" --name "rr-$ARM" --games "$READ_GAMES" \
    --games-per-pair "$GPP" --seed-base "$SEED_BASE" --workers "$WORKERS" --port 50086 --servers 0 \
    --jar "$JAR" --skip-ante >> "$OUT/$ARM.read.log" 2>&1 || { log "read FAILED"; exit 1; }
  ls -dt data/runs/rr-${ARM}arm-s0-* | head -1 | tr -d '\n' > "$OUT/$ARM.read.done"; echo -n "," >> "$OUT/$ARM.read.done"; ls -dt data/runs/rr-${ARM}arm-s1-* | head -1 >> "$OUT/$ARM.read.done"
fi
uv run python scripts/arms_report.py --arm "$ARM=$(cat $OUT/$ARM.read.done)" --out "$OUT/$ARM.read.json" > /dev/null 2>&1
uv run python scripts/paired_arms.py --a "$(cat $OUT/$ARM.read.done)" --b "$(cat $REF_DONE)" 2>&1 | tee "$OUT/paired.txt"
python3 - "$ARM" "$OUT" "$CKPT" "$MARGIN_PP" <<'PY' | tee -a "$OUT/queue.log" > "$OUT/read.md"
import json, re, sys
arm, out, ckpt, margin = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
r = json.load(open(f"{out}/{arm}.read.json"))[arm]
ref = json.load(open("data/runs/resolution-read/alloc.read.json"))["alloc"]
p = open(f"{out}/paired.txt").read()
m = re.search(r"A - B: ([-+][0-9.]+)pp ± ([0-9.]+) \(t=([-0-9.]+), (\d+) up / (\d+) down\)", p)
diff, se = float(m.group(1)), float(m.group(2))
verdict = "CLEARS" if diff >= margin else "MISSES"
print(f"# The margin read: {arm} vs the fresh alloc read of record (seed base 20261001, paired)\n")
print(f"| cell | ckpt | games | decisive | crashes | winrate (network alone, raw) |\n|---|---|---|---|---|---|")
print(f"| alloc (of record) | shakedown-alloc/iter-019 | {ref['games']} | {ref['decisive']} | {ref['crashes']} | {ref['winrate']:.4f} ± {ref['se']:.4f} |")
print(f"| {arm} | {ckpt} | {r['games']} | {r['decisive']} | {r['crashes']} | {r['winrate']:.4f} ± {r['se']:.4f} |\n")
print(f"Paired difference ({arm} − alloc): **{diff:+.2f} ± {se:.2f}pp** (t {m.group(3)}, {m.group(4)} up / {m.group(5)} down)\n")
print(f"**The fixed margin (≥ {margin:+.1f}pp on the point estimate): {verdict}.**")
PY
log "margin read done: $(grep -o 'MISSES\|CLEARS' $OUT/read.md | head -1)"; echo OK > "$OUT/DONE"
