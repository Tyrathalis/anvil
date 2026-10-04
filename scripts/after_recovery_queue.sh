#!/usr/bin/env bash
# THE QUEUE AFTER THE RECOVERY CELL (10-03 17:35): wait for settings-pass5 to leave the box, then THE
# CAST-MASK PAIRED READ — the option-scan restrictions fix (fork 9c589c1ced, forkcheck PASS 17:29, the pin)
# is a serve-path change, so before it serves a run it gets the read the 10-02 routing named: the same
# checkpoint (settings-stopgrad-t3e6/iter-019), the same seeds (seed base 20261003, 1,000 per seat, 5 per
# pair), network alone, on the cast-mask jar; paired game-for-game against the re-measure's arms on the
# shuffle-mark jar (data/runs/ar-stopgradarm-s{0,1}-20261003-*: raw 0.5463 ± 0.0112) at no new control
# games. Pre-registered (running record 10-03 17:35): a correctness item, read for regression — the fix
# removes options the realizer vetoed anyway, so the expectation is a change inside noise; FLAG at a paired
# difference below −1.0pp (the margin convention) or beyond 2 SE either way; the census must show the
# Spider-Man 2099 `restrictions` vetoes gone (the s0 control arm: 1,215 of 1,775) and optmask/restricted rows
# in their place. Exploratory beyond the flag.
# Launch: uv run python -m anvil.runs launch --name after-recovery --dir data/runs/after-recovery \
#   --watch 'data/runs/settings-pass5' --watch 'data/training/settings-recovery' --watch 'data/runs/cm-*' \
#   --stall-min 240 -- bash scripts/after_recovery_queue.sh
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/after-recovery; mkdir -p "$OUT"
CKPT=data/training/settings-stopgrad-t3e6/iter-019/train/last.pt
JAR=$REPO/data/runs/castmask/forge-castmask.jar
REF_DONE=$REPO/data/runs/ante-remeasure/read.done
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "waiting for settings-pass5"
uv run python -m anvil.runs wait --name settings-pass5 >> "$OUT/queue.log" 2>&1; log "settings-pass5 left: $(grep -o '"state": "[a-z]*"' ~/.local/state/anvil/runs/settings-pass5.json)"
sleep 30
[[ -f "$REF_DONE" ]] || { log "no control arms at $REF_DONE"; exit 1; }
log "the cast-mask paired read: ckpt=$CKPT jar=$JAR vs $(cat $REF_DONE)"
if [[ ! -f "$OUT/read.done" ]]; then
  nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT" --name cm-stopgrad --games 1000 --games-per-pair 5 \
    --seed-base 20261003 --workers 24 --port 50090 --servers 0 --jar "$JAR" --skip-ante >> "$OUT/read.log" 2>&1 || { log "read FAILED"; exit 1; }
  ls -dt data/runs/cm-stopgradarm-s0-* | head -1 | tr -d '\n' > "$OUT/read.done"; echo -n "," >> "$OUT/read.done"; ls -dt data/runs/cm-stopgradarm-s1-* | head -1 >> "$OUT/read.done"
fi
uv run python scripts/arms_report.py --arm "castmask=$(cat $OUT/read.done)" --out "$OUT/castmask.read.json" > /dev/null 2>&1
uv run python scripts/paired_arms.py --a "$(cat $OUT/read.done)" --b "$(cat $REF_DONE)" 2>&1 | tee "$OUT/paired.txt"
# the census check: restrictions vetoes by pick, optmask rows, on the s0 arms (cast-mask vs control)
python3 - "$OUT" "$REF_DONE" <<'PY' | tee "$OUT/census.md"
import json, sys, glob, collections
out, ref = sys.argv[1], open(sys.argv[2]).read().strip().split(",")
new = open(f"{out}/read.done").read().strip().split(",")
def census(d):
    vet = collections.Counter(); spidey = 0; optmask = 0
    for f in glob.glob(f"{d}/workers/*/census.jsonl"):
        for l in open(f):
            if '"veto":"restrictions"' in l:
                r = json.loads(l); vet[r.get("pick","")[:30]] += 1
                if r.get("pick","").startswith("Spider-Man 2099"): spidey += 1
            elif '"m":"optmask"' in l:
                optmask += 1
    return sum(vet.values()), spidey, optmask, vet.most_common(3)
print("# The cast-mask census check (restrictions vetoes; optmask rows)\n")
print("| arm | jar | restrictions vetoes | of them Spider-Man 2099 | optmask rows | top picks |\n|---|---|---|---|---|---|")
for label, dirs in (("control (shuffle-mark jar)", ref), ("cast-mask", new)):
    for d in dirs:
        n, sp, om, top = census(d)
        print(f"| {label} / {d.split('/')[-1]} | | {n} | {sp} | {om} | {top} |")
PY
log "paired read done: $(grep -o 'A - B: [^)]*)' $OUT/paired.txt | head -1)"; echo OK > "$OUT/DONE"
