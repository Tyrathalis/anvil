#!/usr/bin/env bash
# THE SEGMENT-3 BOUNDARY CHAIN (10-29; running record 10-24 + ADR-0124 §6): the three box items in one launch, in the
# order that keeps the timed read on a quiet box.
#  1. The ParallelGC forkcheck (WalnutBoat, #contribution-questions 10-23: G1 at 27–42% of Forge's CPU, identical games
#     ≈ 25–30% cheaper under ParallelGC): the launch jar forge-tgtmask3.jar under -XX:+UseParallelGC on the standing
#     500-seed set, compared against the pin's own forkcheck (run-20261004-tgtmask3, the same jar — IDENTICAL on all 500
#     expected: a collector is not a game-path change) and against the 09-16 merge baseline (identical but for the
#     standing seed 20260969). Any mismatch against the pin ⇒ not neutral ⇒ the A/B is skipped and the flag stays out.
#  2. The timed A/B on iter-301 for the loop's two workloads — network-alone and with-lookahead under RECIPE + the
#     checkpoint's alloc tau — 200 games / seat per arm, the control (the chain's JVM opts) then ParallelGC on the SAME
#     seeds (20261029), so the games pair: the read is the per-game ms paired on seed, the arm wall, and the outcome
#     agreement (0 up / 0 down = identical play, the forkcheck's promise in the harness).
#  3. The labeler re-price for ADR-0124's segment-3 bank: bench_labeler on iter-301, the launch jar, K=8, census off.
# Launch (the box quiet): uv run python -m anvil.runs launch --name seg3-boundary --dir data/runs/seg3-boundary \
#   --launched-by '<ListAgents name> [<ref>]' --watch 'data/forkcheck/run-20261029-parallelgc' --watch 'data/runs/gc-*' \
#   --watch 'data/runs/labelbench-w*' --stall-min 90 -- bash scripts/seg3_boundary_chain.sh
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/seg3-boundary; mkdir -p "$OUT"
JAR=${JAR:-$REPO/data/runs/tgtmask/forge-tgtmask3.jar}
CKPT=${CKPT:-data/training/big-run/iter-301/train/last.pt}
FC=$REPO/data/forkcheck/run-20261029-parallelgc; PIN_FC=$REPO/data/forkcheck/run-20261004-tgtmask3
SB=${SB:-20261029}; GAMES=${GAMES:-200}; WORKERS=${WORKERS:-24}
GC_FLAG="-XX:+UseParallelGC"; BASE_JVM="-Danvil.crash.trace=true"
source scripts/recipe.sh
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
[[ -f "$JAR" ]] || { log "no jar at $JAR"; exit 1; }

# ---- 1. the forkcheck ----
if [[ ! -f "$OUT/forkcheck.done" ]]; then
  log "forkcheck start: jar=$JAR ($(cat data/runs/tgtmask/forge-tgtmask3.commit 2>/dev/null)) JVM_ARGS=$GC_FLAG out=$FC"
  JVM_ARGS="$GC_FLAG" N_GAMES=500 SEED=20260703 JAR="$JAR" bash scripts/forkcheck/run_forkcheck.sh "$FC" | tee -a "$OUT/queue.log"
  pid=$(cat "$FC/run.pid")
  until [ ! -d /proc/$pid ] || { [ -f "$FC/results.jsonl" ] && [ "$(wc -l < "$FC/results.jsonl")" -ge 500 ]; }; do sleep 60; touch "$OUT/.waiting"; done
  uv run python scripts/forkcheck/compare.py "$FC" --baseline "$PIN_FC" | tee "$FC/compare-vs-pin.txt" | tee -a "$OUT/queue.log"
  uv run python scripts/forkcheck/compare.py "$FC" | tee "$FC/compare.txt" | tee -a "$OUT/queue.log"
  echo OK > "$OUT/forkcheck.done"
fi
# the pin comparison's verdict (compare.py prints "main-trace hashes identical: N/500" and one "  DIFF seed S" line per
# miss): PASS = every differing seed is the standing non-deterministic seed 20260969 (it differs between the pin's own
# run and the baseline too — three hashes across three JVM launches; the ADR-0025 proof reads "identical but for
# 20260969"). The first launch's grep missed the colon and skipped the A/B on an empty count (fixed 20:30).
VERDICT=$(python3 - "$FC/compare-vs-pin.txt" <<'PV'
import re, sys
t = open(sys.argv[1]).read()
m = re.search(r"identical: (\d+)/(\d+)", t); diffs = re.findall(r"DIFF seed (\d+)", t)
ok = m and set(diffs) <= {"20260969"} and int(m.group(1)) + len(diffs) == int(m.group(2))
print(("PASS" if ok else "FAIL") + f" identical {m.group(1) if m else '?'}/{m.group(2) if m else '?'} diffs {diffs}")
PV
)
if [[ "$VERDICT" != PASS* ]]; then
  log "forkcheck vs the pin: $VERDICT — ParallelGC is NOT trace-identical on this jar; the A/B is skipped"
  echo SKIPPED > "$OUT/ab.done"
else
  log "forkcheck vs the pin: $VERDICT — ParallelGC is trace-identical but for the standing seed; the A/B runs"
fi

# ---- 2. the timed A/B ----
tau=$(uv run python -c "from anvil.training.selfplay import alloc_tau_of; t=alloc_tau_of('$CKPT'); print('' if t is None else f'{t:.5f}')" 2>/dev/null | tail -1)
FA="$RECIPE"; [[ -n "$tau" ]] && FA="$RECIPE -searchalloc $tau -searchfloor 0.1"
# ab_arm <tag> <na|la> <jvm opts> : one final_read arm pair -> $OUT/<tag>.done (the two arm dirs) + $OUT/<tag>.wall
ab_arm() {
  local tag=$1 mode=$2 jvm=$3 extra=() t0 t1
  [[ -f "$OUT/$tag.done" ]] && return 0
  [[ $mode == la ]] && extra=(--forge-args "$FA" --labels)
  log "A/B arm $tag ($mode): JVM='$jvm' games=$GAMES/seat seed_base=$SB"
  t0=$(date +%s)
  ANVIL_EXTRA_JVM_OPTS="$jvm" nice -n 19 uv run python scripts/final_read.py --ckpt "$CKPT" --name "gc-$tag" --games "$GAMES" --games-per-pair 5 \
    --seed-base "$SB" --workers "$WORKERS" --port 50086 --servers 0 --jar "$JAR" --skip-ante "${extra[@]}" >> "$OUT/$tag.log" 2>&1 \
    || { log "A/B arm $tag FAILED"; return 1; }
  t1=$(date +%s); echo $((t1 - t0)) > "$OUT/$tag.wall"
  ls -dt "data/runs/gc-${tag}arm-s0-"* | head -1 | tr -d '\n' > "$OUT/$tag.done"; echo -n "," >> "$OUT/$tag.done"; ls -dt "data/runs/gc-${tag}arm-s1-"* | head -1 >> "$OUT/$tag.done"
  log "A/B arm $tag done: wall $((t1 - t0)) s"
}
if [[ ! -f "$OUT/ab.done" ]]; then
  ab_arm na-ctl na "$BASE_JVM" && ab_arm na-pgc na "$BASE_JVM $GC_FLAG" && ab_arm la-ctl la "$BASE_JVM" && ab_arm la-pgc la "$BASE_JVM $GC_FLAG" || { log "A/B incomplete"; exit 1; }
  uv run python - "$OUT" <<'PY' | tee "$OUT/ab.md" | tee -a "$OUT/queue.log"
import json, sys
from pathlib import Path
out = Path(sys.argv[1])
def games(done):
    rows = {}
    for k, d in enumerate(Path(done).read_text().strip().split(",")):
        for line in (Path(d) / "games.jsonl").read_text().splitlines():
            g = json.loads(line); rows[(k, g["i"])] = g
    return rows
print("# The ParallelGC timed A/B (10-29): iter-301 on forge-tgtmask3.jar, 200 games / seat per arm, seeds 20261029, the control (G1) vs -XX:+UseParallelGC on the same seeds\n")
print("| workload | arm | wall s | games/h (wall) | sum ms (paired games) | ms per game (median) | ratio pgc/ctl (paired ms) | outcomes up / down |")
print("|---|---|---|---|---|---|---|---|")
for w in ("na", "la"):
    c, p = games(out / f"{w}-ctl.done"), games(out / f"{w}-pgc.done")
    common = [k for k in c if k in p and c[k].get("status") == "won" and p[k].get("status") == "won" and c[k]["seed"] == p[k]["seed"]]
    sc = sum(c[k]["ms"] for k in common); sp = sum(p[k]["ms"] for k in common)
    up = sum(1 for k in common if (p[k]["winner"] or "").startswith("Anvil") and not (c[k]["winner"] or "").startswith("Anvil"))
    dn = sum(1 for k in common if (c[k]["winner"] or "").startswith("Anvil") and not (p[k]["winner"] or "").startswith("Anvil"))
    for name, g, s in (("ctl (G1)", c, sc), ("ParallelGC", p, sp)):
        wall = int((out / f"{w}-{'ctl' if name.startswith('ctl') else 'pgc'}.wall").read_text())
        ms = sorted(x["ms"] for x in g.values() if x.get("ms"))
        n = len(g)
        print(f"| {w} | {name} | {wall} | {n / (wall / 3600):.0f} | {s / 1000:.0f} s over {len(common)} | {ms[len(ms) // 2] / 1000:.1f} s | {'' if name.startswith('ctl') else f'{sp / sc:.3f}'} | {'' if name.startswith('ctl') else f'{up} / {dn}'} |")
print("\nRead: identical outcomes on every paired game is the harness-side identity check (the forkcheck's on the jar alone); the paired ms ratio is the per-game cost under each collector with the same games; the wall adds the server start and the straggler tail.")
PY
  echo OK > "$OUT/ab.done"
fi

# ---- 3. the labeler re-price ----
if [[ ! -f "$OUT/labeler.done" ]]; then
  log "labeler re-price: ckpt=$CKPT jar=$JAR K=8 points=4 games=160 workers=$WORKERS servers=2"
  nice -n 19 uv run python scripts/bench_labeler.py --ckpt "$CKPT" --jar "$JAR" --workers "$WORKERS" --servers 2 --port 50086 \
    --seed-base "$SB" --out "$OUT/labeler-bench.json" >> "$OUT/labeler.log" 2>&1 || { log "labeler bench FAILED"; exit 1; }
  echo OK > "$OUT/labeler.done"
  log "labeler bench: $(uv run python -c "import json; d=json.load(open('$OUT/labeler-bench.json')); r=d.get('bench') or d; print({k: r.get(k) for k in ('pos_per_h','pos_per_h_per_worker','labels','elapsed_s','mainline_games_per_h')})" 2>/dev/null)"
fi
log "DONE"; echo OK > "$OUT/DONE"
