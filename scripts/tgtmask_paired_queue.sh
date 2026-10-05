#!/usr/bin/env bash
# THE UNION TARGET MASK'S PAIRED READ (ADR-0122, 10-04), queued behind the gate chain (tgtmask-agree):
# runs ONLY if the agreement check cleared (validate exit=0 — zero heuristic-chosen targets outside the
# mask); a failed check leaves the read unlaunched and this queue FAILED (the check-in relays it). The read:
# the same checkpoint the cast-mask read served (settings-stopgrad-t3e6/iter-019), the same seeds (seed
# base 20261003, 1,000 per seat, 5 per pair), network alone, the mask jar, THE DECODER MASKED (the server's
# default from this worktree's code) — paired game-for-game against the cast-mask read's arms
# (data/runs/cm-stopgradarm-s{0,1}-20261004-*: raw 0.5405 ± 0.0111, the decoder unmasked on a jar whose game
# path is identical — the forkcheck's proof) at no new control games. PRE-REGISTERED (running record
# 10-04): a correctness item read for regression and for the veto class it was built to remove — FLAG at a
# paired difference below −1.0pp (the margin convention) or beyond 2 SE either way; the census must show the
# `no_shape_fit` vetoes fall against the control arms; the TIMING CHECK is this read's generation wall
# against the cast-mask read's 43 min on the same seeds and worker count: the mask may cost at most 5% (a
# wall above 45 min flags the enumeration; routed to the Obs writer's cost before it serves a run).
# Exploratory beyond the flags.
# Launch (from the bridge worktree): uv run python -m anvil.runs launch --name tgtmask-paired \
#   --dir data/runs/tgtmask-paired --launched-by '<ListAgents name> [<ref>]' --watch 'data/runs/tm-*' \
#   --stall-min 240 -- bash scripts/tgtmask_paired_queue.sh
set -u
TAG=${TAG:-}   # the gate chain's suffix (see tgtmask_agree_queue.sh); the read's own arms carry it too
REPO=${REPO:-$(cd "$(dirname "$0")/.." && pwd)}; cd "$REPO"
OUT=$REPO/data/runs/tgtmask-paired$TAG; mkdir -p "$OUT"
GATE=$REPO/data/runs/tgtmask-agree$TAG
CKPT=data/training/settings-stopgrad-t3e6/iter-019/train/last.pt
JAR=$REPO/data/runs/tgtmask/forge-tgtmask$TAG.jar
REF_DONE=$REPO/data/runs/after-recovery/read.done   # the cast-mask read's arms (unmasked decoder)
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "waiting for the gate chain (tgtmask-agree)"
uv run python -m anvil.runs wait --name "tgtmask-agree$TAG" >> "$OUT/queue.log" 2>&1
log "gate chain left: $(grep -o '"state": "[a-z]*"' ~/.local/state/anvil/runs/tgtmask-agree$TAG.json)"
sleep 30
[[ -f "$GATE/DONE" ]] || { log "gate chain did not finish (no DONE)"; exit 1; }
# the gate reads the MASK's numbers (zero targets outside, zero casts on unfit options), not the validator's
# exit code — that code also carries the option-mask check (chosen host not among the scan's options), a
# different instrument's finding (routed 10-04: King T'Challa's back face, Dargo, X spells)
VAL=${VAL:-$GATE/validate.txt}
LINE=$(grep -m1 'target mask (ADR-0122)' "$VAL")
# The gate is the MASK's clause: zero legal targets outside. The unfit flag ("tz") feeds only the default-off
# --prune-unfit, so its count is logged beside the verdict and does not hold the read (10-04: Cryptic Command's
# stale bound mode read as unfit once in 107K casts; fixed on the fork, verified on the next labelled store before
# the prune is ever turned on).
if ! echo "$LINE" | grep -q " 0 OUTSIDE the mask,"; then
  log "AGREEMENT CHECK NOT MET — the paired read stays unlaunched: $LINE"; tail -n 20 "$VAL" | tee -a "$OUT/queue.log"; exit 1
fi
log "agreement check CLEARED (the mask's clause): $LINE"
[[ -f "$REF_DONE" ]] || { log "no control arms at $REF_DONE"; exit 1; }
log "the paired read: ckpt=$CKPT jar=$JAR (decoder masked) vs $(cat $REF_DONE)"
T0=$(date +%s)
if [[ ! -f "$OUT/read.done" ]]; then
  nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT" --name "tm$TAG-stopgrad" --games 1000 --games-per-pair 5 \
    --seed-base 20261003 --workers 24 --port 50091 --servers 0 --jar "$JAR" --skip-ante >> "$OUT/read.log" 2>&1 || { log "read FAILED"; exit 1; }
  ls -dt "data/runs/tm$TAG-stopgradarm-s0-"* | head -1 | tr -d '\n' > "$OUT/read.done"; echo -n "," >> "$OUT/read.done"; ls -dt "data/runs/tm$TAG-stopgradarm-s1-"* | head -1 >> "$OUT/read.done"
  echo "wall_s=$(( $(date +%s) - T0 ))" > "$OUT/wall.txt"
fi
uv run python scripts/arms_report.py --arm "tgtmask=$(cat $OUT/read.done)" --out "$OUT/tgtmask.read.json" > /dev/null 2>&1
uv run python scripts/paired_arms.py --a "$(cat $OUT/read.done)" --b "$(cat $REF_DONE)" 2>&1 | tee "$OUT/paired.txt"
# the census check: vetoes by reason (no_shape_fit is the class the mask addresses), masked vs control arms
python3 - "$OUT" "$REF_DONE" <<'PY' | tee "$OUT/census.md"
import json, sys, glob, collections
out, ref = sys.argv[1], open(sys.argv[2]).read().strip().split(",")
new = open(f"{out}/read.done").read().strip().split(",")
def census(d):
    vet = collections.Counter(); casts = 0; reask = 0
    for f in glob.glob(f"{d}/workers/*/census.jsonl"):
        for l in open(f):
            if '"by":"bridge"' not in l or '"oneshot":true' not in l:
                continue
            r = json.loads(l)
            if r.get("copy"):
                continue
            if "veto" in r:
                vet[r["veto"]] += 1
                if r.get("reask"):
                    reask += 1
            else:
                casts += 1
    return casts, sum(vet.values()), dict(vet.most_common(6))
print("# The union-target-mask census check (mainline bridged casts; vetoes by reason)\n")
print("| arm | casts | vetoes | by reason |\n|---|---|---|---|")
for label, dirs in (("control (cast-mask jar, decoder unmasked)", ref), ("masked decoder (mask jar)", new)):
    for d in dirs:
        c, v, top = census(d)
        print(f"| {label} / {d.split('/')[-1]} | {c} | {v} | {top} |")
PY
log "paired read done: $(grep -o 'A - B: [^)]*)' $OUT/paired.txt | head -1); $(cat $OUT/wall.txt 2>/dev/null)"; echo OK > "$OUT/DONE"
