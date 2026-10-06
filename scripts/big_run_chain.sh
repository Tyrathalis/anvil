#!/usr/bin/env bash
# THE BIG RUN (ADR-0123, 10-05 late evening) — the single source of the recipe of record. One selfplay loop
# (`big-run`), warm-started from the WEIGHTS of shakedown-alloc/iter-019, under the alloc search recipe
# (scripts/recipe.sh RECIPE + the allocation head) and the rung-2 value recipe (the head-only anchor at 0.1,
# the value gradient stopped at the trunk, trunk lr 3e-6 / head lr 1e-4), drills OFF, 24 workers x 2 servers
# on forge-tgtmask3.jar (fork 5bd040351f) with the decoder MASKED (the server's default). Six weekly SEGMENTS
# by the loop's wall budget (--wall-hours 168 x segment; wall_used_s persists, so a relaunch resumes the same
# loop with its window, ladder and drift series intact — never a chained loop; the standing rule ADR-0123 born).
#
# The chain, idempotent on every relaunch (a reboot's --resume-on-gone, a pause, the next segment):
#   step 0 (once)  the START-POINT READS on the launch jar, decoder masked, one fixed seed set for the whole
#                  series (SEED_BASE 20261006, the user's call 10-05): the ERA REFERENCE d6-run11/iter-019
#                  network-alone at 2,000 games (the promotion bar's base = this read + 2.5pp; the 0.534 of
#                  ADR-0123 §1 was the stopgrad checkpoint's tm2 read, misattributed — the reference had never
#                  been read masked; ADR-0123 addendum 10-05), the WARM START shakedown-alloc/iter-019
#                  network-alone at 2,000 (the kill rule's "flat" base) and with-lookahead at 1,000 under
#                  RECIPE + the ckpt's own alloc tau (the loop's search_forge_args derivation, so the read plays
#                  the run's behavior policy).
#   segment N      the loop with --wall-hours 168*N (N from $OUT/segment; 1 if absent) and the Spearman guard
#                  floor 0.15 for N=1, 0.30 after (ADR-0123 §2); at the wall stop the SEGMENT READS on the
#                  loop's final checkpoint (2,000 network-alone + 1,000 with-lookahead, the same seeds; paired
#                  game-for-game against the reference and the warm start at no new games), the row in read.md,
#                  seg-N.done, exit 0 (the run reads `done`). Continuing is the user's go:
#                      echo $((N+1)) > data/runs/big-run/segment && uv run python -m anvil.runs relaunch --name big-run
#                  A chain that blocked on a go-file would trip the stall alert every 3 h while it waited.
#   mid-segment    a reboot relaunches the chain (--resume-on-gone): the loop resumes from loop_state.json (the
#                  batch in flight regenerates, <= ~35 min); a read that finished keeps its .done marker.
#                  `anvil.runs pause --name big-run --wait` stops the loop between iterations (<= 1.5 h); the
#                  chain exits 0 and `relaunch` resumes it.
# Pre-registered (ADR-0123 §4-5): PROMOTION >= +2.5pp network-alone over the reference's masked read at 2,000
# games (the paired close read confirms); KILL at segment 3's close: with-lookahead >= 2 SE above its start read
# while network-alone within 1 SE of the warm start's; TRIPLINE: both flat with the Spearman flat -> the value
# head; the Spearman guard halts a falling head. Mid-run reads are for the guards, the gap and the Spearman
# only; the run's close is the standard 2,000-game read on FRESH seeds + the paired read vs the reference at
# 2,500 per seat (CLOSE=1 below, after the user's call).
# Launch (the box quiet, main at the chain's commit; the kernel / driver / JDK pinned in IgnorePkg):
#   uv run python -m anvil.runs launch --name big-run --dir data/runs/big-run --resume-on-gone \
#     --launched-by '<ListAgents name> [<ref>]' --watch 'data/training/big-run' --watch 'data/runs/br*' \
#     --stall-min 180 -- bash scripts/big_run_chain.sh
#   env: SEED_BASE (20261006), SEG_HOURS (168), JAR, START, REF, WORKERS (24), READ_GAMES (1000 / seat),
#        LA_GAMES (500 / seat), CLOSE (unset; 1 = the close reads instead of a segment), CLOSE_SEED_BASE
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
NAME=big-run; LOOP=data/training/$NAME
OUT=$REPO/data/runs/$NAME; mkdir -p "$OUT"
JAR=${JAR:-$REPO/data/runs/tgtmask/forge-tgtmask3.jar}            # fork 5bd040351f, forkcheck PASS 10-05 00:15
START=${START:-data/training/shakedown-alloc/iter-019/train/last.pt}   # the warm start (ADR-0123 §1)
REF=${REF:-data/training/d6-run11/iter-019/train/last.pt}              # the era reference (the bar's base)
BANK=${BANK:-data/runs/m12-build1}                                      # the state bank + the value anchor's terms
SEED_BASE=${SEED_BASE:-20261006}; SEG_HOURS=${SEG_HOURS:-168}
WORKERS=${WORKERS:-24}; READ_GAMES=${READ_GAMES:-1000}; LA_GAMES=${LA_GAMES:-500}
SEGMENT=$(cat "$OUT/segment" 2>/dev/null || echo 1)
. "$REPO/scripts/recipe.sh"   # RECIPE — the one definition of the search recipe
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
[[ -f "$OUT/read.md" ]] || printf '# The big run (ADR-0123) — the start-point and segment reads\n\nAll reads: the launch jar (forge-tgtmask3.jar, 5bd040351f), the decoder masked, seed base %s, network-alone 2,000 games / with-lookahead 1,000 under RECIPE + the checkpoint'"'"'s alloc tau; raw. Paired columns: game-for-game on the same seeds (paired_arms.py).\n\n| point | wall h | iterations | games | ckpt | network-alone | with-lookahead | vs reference (paired) | vs warm start (paired) | last Spearman |\n|---|---|---|---|---|---|---|---|---|---|\n' "$SEED_BASE" > "$OUT/read.md"

tau_of() { uv run python -c "from anvil.training.selfplay import alloc_tau_of; t=alloc_tau_of('$1'); print('' if t is None else f'{t:.5f}')" 2>/dev/null | tail -1; }
# read_na <tag> <ckpt> [<seed base>] : the network-alone read, READ_GAMES per seat -> $OUT/<tag>.na.done (the two arm dirs)
read_na() {
  local tag=$1 ckpt=$2 sb=${3:-$SEED_BASE}
  [[ -f "$OUT/$tag.na.done" ]] && return 0
  log "read $tag network-alone: ckpt=$ckpt games=$READ_GAMES/seat seed_base=$sb"
  nice -n 19 uv run python scripts/final_read.py --ckpt "$ckpt" --name "br-$tag" --games "$READ_GAMES" --games-per-pair 5 \
    --seed-base "$sb" --workers "$WORKERS" --port 50086 --servers 0 --jar "$JAR" --skip-ante >> "$OUT/$tag.na.log" 2>&1 \
    || { log "read $tag network-alone FAILED"; return 1; }
  ls -dt "data/runs/br-${tag}arm-s0-"* | head -1 | tr -d '\n' > "$OUT/$tag.na.done"; echo -n "," >> "$OUT/$tag.na.done"; ls -dt "data/runs/br-${tag}arm-s1-"* | head -1 >> "$OUT/$tag.na.done"
}
# read_la <tag> <ckpt> : the with-lookahead read under the run's behavior policy, LA_GAMES per seat -> $OUT/<tag>.la.done
#   (--labels beside the forge args: the fork refuses -search without -labels — the 10-05 22:35 failure; the loop passes it too)
read_la() {
  local tag=$1 ckpt=$2 tau fa
  [[ -f "$OUT/$tag.la.done" ]] && return 0
  tau=$(tau_of "$ckpt"); fa="$RECIPE"
  [[ -n "$tau" ]] && fa="$RECIPE -searchalloc $tau -searchfloor 0.1" || log "read $tag: NO alloc tau on $ckpt — the uniform rate"
  log "read $tag with-lookahead: ckpt=$ckpt games=$LA_GAMES/seat forge_args='$fa'"
  nice -n 19 uv run python scripts/final_read.py --ckpt "$ckpt" --name "brla-$tag" --games "$LA_GAMES" --games-per-pair 5 \
    --seed-base "$SEED_BASE" --workers "$WORKERS" --port 50086 --servers 0 --jar "$JAR" --skip-ante --forge-args "$fa" --labels >> "$OUT/$tag.la.log" 2>&1 \
    || { log "read $tag with-lookahead FAILED"; return 1; }
  ls -dt "data/runs/brla-${tag}arm-s0-"* | head -1 | tr -d '\n' > "$OUT/$tag.la.done"; echo -n "," >> "$OUT/$tag.la.done"; ls -dt "data/runs/brla-${tag}arm-s1-"* | head -1 >> "$OUT/$tag.la.done"
}
winrate() { uv run python scripts/arms_report.py --arm "$1=$(cat "$2")" --out "${2%.done}.json" 2>/dev/null | grep -o "winrate [0-9.]* ± [0-9.]*" | head -1; }
paired() { # paired <a.done> <b.done> -> "A - B: ..." (the same seeds)
  [[ -f "$1" && -f "$2" ]] || { echo "n/a"; return; }
  uv run python scripts/paired_arms.py --a "$(cat "$1")" --b "$(cat "$2")" 2>/dev/null | grep -o 'A - B: [^)]*)' | head -1
}
spearman_last() { python3 -c "
import json,glob
fs=sorted(glob.glob('$LOOP/iter-*/state-ranking.json'))
r=json.load(open(fs[-1])) if fs else {}
print(f\"{r.get('spearman')} ± {r.get('se_boot')} ({fs[-1].split('/')[-2]})\" if fs else 'n/a')" 2>/dev/null; }
row() { printf '| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |\n' "$@" >> "$OUT/read.md"; }

# ---- the close (CLOSE=1, the user's call at the run's end): the number of record on FRESH seeds + the paired
#      read vs the reference at 2,500 per seat on those seeds (ADR-0123 §4) ----
if [[ "${CLOSE:-}" == 1 ]]; then
  CSB=${CLOSE_SEED_BASE:?set CLOSE_SEED_BASE (fresh seeds for the close)}
  FINAL=$(python3 -c "import json; print(json.load(open('$LOOP/loop_state.json'))['ckpt'])")
  log "THE CLOSE: final=$FINAL fresh seed base $CSB"
  read_na close "$FINAL" "$CSB" || exit 1
  READ_GAMES=2500 read_na close-paired "$FINAL" "$CSB" || exit 1
  READ_GAMES=2500 read_na ref-paired "$REF" "$CSB" || exit 1
  row "CLOSE (fresh seeds $CSB)" "" "" "" "$FINAL" "$(winrate close $OUT/close.na.done)" "" "$(paired $OUT/close-paired.na.done $OUT/ref-paired.na.done) [2,500/seat]" "" "$(spearman_last)"
  log "close reads done: $(tail -1 $OUT/read.md)"; echo OK > "$OUT/CLOSE.done"; exit 0
fi

# ---- step 0: the start-point reads, once ----
if [[ ! -f "$OUT/start.done" ]]; then
  log "big-run chain start: jar=$JAR start=$START ref=$REF seed_base=$SEED_BASE segment=$SEGMENT"
  read_na ref "$REF" || exit 1
  read_na start "$START" || exit 1
  read_la start "$START" || exit 1
  row "era reference d6-run11/iter-019" "" "" "" "$REF" "$(winrate ref $OUT/ref.na.done)" "" "" "" ""
  row "warm start shakedown-alloc/iter-019" "" "" "" "$START" "$(winrate start $OUT/start.na.done)" "$(winrate start-la $OUT/start.la.done)" "$(paired $OUT/start.na.done $OUT/ref.na.done)" "" ""
  echo ok > "$OUT/start.done"
  log "start-point reads done: ref $(winrate ref $OUT/ref.na.done) | start $(winrate start $OUT/start.na.done) | start+la $(winrate start-la $OUT/start.la.done)"
fi

# ---- segment N ----
if [[ -f "$OUT/seg-$SEGMENT.done" ]]; then
  log "segment $SEGMENT is closed already — the next segment: echo $((SEGMENT+1)) > $OUT/segment && anvil.runs relaunch --name $NAME"; exit 0
fi
WALL=$((SEG_HOURS * SEGMENT)); FLOOR=0.30; [[ $SEGMENT -eq 1 ]] && FLOOR=0.15
WALL_DONE=$(python3 -c "import json,os; s=json.load(open('$LOOP/loop_state.json')) if os.path.exists('$LOOP/loop_state.json') else {}; print(int(float(s.get('wall_used_s',0)) >= $WALL*3600))")
if [[ $WALL_DONE -eq 0 ]]; then
  # a previous segment's WALL-STOP marker: the loop reads only its budget, the marker is for the chain
  [[ -f "$LOOP/WALL-STOP" ]] && mv "$LOOP/WALL-STOP" "$LOOP/WALL-STOP.seg$((SEGMENT-1))"
  log "segment $SEGMENT: the loop to --wall-hours $WALL (spearman floor $FLOOR); resumes from $LOOP/loop_state.json if present"
  uv run python -m anvil.training.selfplay --name "$NAME" --ckpt "$START" --iterations 2000 --wall-hours "$WALL" \
    --games 480 --games-per-pair 2 --workers "$WORKERS" --chunk 30 --port 50063 --seed-base 20260921 \
    --temperature 1.0 --replay 4 --fresh-weight 1.0 --replay-weight 0.33 --rl-workers 12 --epochs 1 --lr 1e-5 \
    --ent-weight 0.003 --ent-floor 0.08 --rl-seg 128 --guard-kl 0.06 --guard-ent-mult 2.0 --guard-veto-mult 1.5 \
    --guard-casts-floor 0.8 --penalty 0.02 --heur-frac 0.5 --value-weight 0.5 --traj-per-step 4 \
    --arms-every 5 --arms-pairs data/runs/d5arm-d0-s0-20260714-143546/pairs.txt --arms-games 200 --arms-seed-base 20260710 --arms-lookahead on \
    --reask --jar "$JAR" --search-recipe "$RECIPE" --search-alloc head --search-floor 0.1 \
    --distill-carry-w --alloc-carry-w --state-bank "$BANK" --guard-spearman-floor "$FLOOR" \
    --value-anchor "$BANK" --anchor-weight 0.1 --value-stopgrad-trunk --trunk-lr 3e-6 --value-head-lr 1e-4 \
    --grad-norm-every 50 >> "$OUT/seg-$SEGMENT.loop.log" 2>&1
  rc=$?
  if [[ -f "$LOOP/STOP" ]]; then log "segment $SEGMENT paused (STOP present) — the chain exits; relaunch resumes"; exit 0; fi
  if [[ $rc -ne 0 && ! -f "$LOOP/WALL-STOP" ]]; then log "segment $SEGMENT loop FAILED rc=$rc (a guard halt or a crash; read $OUT/seg-$SEGMENT.loop.log)"; exit 1; fi
  [[ -f "$LOOP/WALL-STOP" ]] || { log "segment $SEGMENT: the loop exited without WALL-STOP (iterations exhausted?) rc=$rc"; exit 1; }
fi
FINAL=$(python3 -c "import json; print(json.load(open('$LOOP/loop_state.json'))['ckpt'])")
ITERS=$(python3 -c "import json; print(json.load(open('$LOOP/loop_state.json'))['iteration'])")
WALL_H=$(python3 -c "import json; print(round(json.load(open('$LOOP/loop_state.json')).get('wall_used_s',0)/3600,1))")
log "segment $SEGMENT at the wall: $ITERS iterations, $WALL_H h, final $FINAL — the segment reads"
read_na "seg$SEGMENT" "$FINAL" || exit 1
read_la "seg$SEGMENT" "$FINAL" || exit 1
row "segment $SEGMENT" "$WALL_H" "$ITERS" "$((ITERS*480))" "$FINAL" "$(winrate seg$SEGMENT $OUT/seg$SEGMENT.na.done)" "$(winrate seg$SEGMENT-la $OUT/seg$SEGMENT.la.done)" \
    "$(paired $OUT/seg$SEGMENT.na.done $OUT/ref.na.done)" "$(paired $OUT/seg$SEGMENT.na.done $OUT/start.na.done)" "$(spearman_last)"
echo ok > "$OUT/seg-$SEGMENT.done"
log "segment $SEGMENT CLOSED: $(tail -1 $OUT/read.md)"
log "the next segment (the user's go): echo $((SEGMENT+1)) > $OUT/segment && uv run python -m anvil.runs relaunch --name $NAME"
echo OK > "$OUT/DONE"
