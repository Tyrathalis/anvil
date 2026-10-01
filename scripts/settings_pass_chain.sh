#!/usr/bin/env bash
# ADR-0119 step 1 + the ADR-0115 verdict addendum (09-27): THE SETTINGS PASS ON ALLOC — two cells at
# EQUAL BOX TIME to the shakedown's arms (30 h each, --wall-hours), sequential, each a selfplay.py loop
# from the SAME day-zero build (m12-build4-e1a-tgt) the shakedown's arms started from, on the pin of
# record's jar (the certifier merge 05fea7938d, forkcheck 499/500 = behavior-identical to the census jar,
# ADR-0117 / ADR-0025), the shakedown's loop settings and seed base, 24 workers x 2 servers, drills OFF;
# each cell closes with the 2,000-game read vs the heuristic (network alone, raw) -> read.md.
#   anchor        the alloc arm (RECIPE + the allocation head) + the VALUE ANCHOR (rl.py --value-anchor:
#                 the Build 1 replay terms, one mini-batch per step, weight 0.5) + the gn_* row.
#                 Pre-registered bar (ADR-0118 item 3): the state-ranking Spearman within one bootstrap
#                 SE of the day-zero 0.374 across the pass's iterations while the network-alone read is
#                 not worse than the un-anchored winner (shakedown-alloc 0.5405 +/- 0.0111). Misses ->
#                 the ADR-0119 ladder (a lower --value-weight; stop-grad at the trunk; a separate trunk).
#   shallowalloc  the allocation head over the one-roll search (SHALLOW + head; no anchor) — the verdict's
#                 first search cell; read against shakedown-alloc 0.5405 and shakedown-shallow 0.5320.
# Both cells start from day-zero (not the alloc arm's warm start) so every clause reads exactly as
# registered against the shakedown's numbers; the anchor's RECOVERY of a drifted trunk is a separate
# read (a short Spearman-only continuation from shakedown-alloc/iter-019) if the anchor cell clears.
# Launch: uv run python -m anvil.runs launch --name settings-pass --dir data/runs/settings-pass --resume-on-gone \
#           --watch 'data/training/settings-*' --watch 'data/runs/settings-*' --watch 'data/runs/sp*' \
#           --stall-min 180 -- bash scripts/settings_pass_chain.sh
#   env: WALL_HOURS (30), ARMS ("anchor shallowalloc"), JAR, CKPT, WORKERS (24), READ_GAMES (1000 / seat),
#        BANK (data/runs/m12-build1), ANCHOR_WEIGHT (0.5)
# Pause / resume (a maintenance reboot): anvil.runs pause --name settings-pass --wait ... anvil.runs relaunch --name settings-pass
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/${CHAIN_OUT:-settings-pass}; mkdir -p "$OUT"  # 09-29: chain2 writes to settings-pass2
JAR=${JAR:-$REPO/data/runs/certmerge/forge-certmerge.jar}
CKPT=${CKPT:-data/training/m12-build4-e1a-tgt/last.pt}  # the shakedown's day-zero (ADR-0116)
BANK=${BANK:-data/runs/m12-build1}; ANCHOR_WEIGHT=${ANCHOR_WEIGHT:-0.5}
WALL_HOURS=${WALL_HOURS:-30}; ARMS=${ARMS:-anchor shallowalloc}; WORKERS=${WORKERS:-24}; READ_GAMES=${READ_GAMES:-1000}
. "$REPO/scripts/recipe.sh"  # RECIPE / SHALLOW — the one definition
# 09-28: every worker JVM prints a crash's stack trace (the fork's anvil.crash.trace switch, read by the
# harness from ANVIL_EXTRA_JVM_OPTS) — the anchor cell's StackOverflowError class (2 in 4,800 games; a
# class the shakedown never produced) cannot be attributed by seed replay (search lines are
# serving-environment dependent), so the next occurrence carries its trace.
export ANVIL_EXTRA_JVM_OPTS="${ANVIL_EXTRA_JVM_OPTS:--Danvil.crash.trace=true}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
[[ -f "$OUT/read.md" ]] || printf '# The settings pass on alloc (ADR-0119 step 1 + the ADR-0115 verdict) — per-cell reads\n\nReferences (the shakedown, census jar, same day-zero): dayzero 0.5185 ± 0.0112 · alloc 0.5405 ± 0.0111 · shallow 0.5320 ± 0.0112; day-zero state-ranking Spearman 0.374 ± 0.024.\n\n| cell | wall h | iterations | games | final ckpt | 2,000-game read (network alone) | last lookahead arm |\n|---|---|---|---|---|---|---|\n' > "$OUT/read.md"
log "settings-pass chain start jar=$JAR ckpt=$CKPT wall=${WALL_HOURS}h/cell arms='$ARMS' bank=$BANK anchor_weight=$ANCHOR_WEIGHT"
for arm in $ARMS; do
  case $arm in
    anchor|anchor-w*) FARGS="$RECIPE"; ALLOC=head; EXTRA="--value-anchor $BANK --anchor-weight $ANCHOR_WEIGHT --grad-norm-every 50" ;;  # anchor-w01 = rung 1' (09-29): ANCHOR_WEIGHT=0.1
    shallowalloc) FARGS="$SHALLOW"; ALLOC=head; EXTRA="--grad-norm-every 50" ;;
    stopgrad) FARGS="$RECIPE"; ALLOC=head; EXTRA="--value-anchor $BANK --anchor-weight $ANCHOR_WEIGHT --value-stopgrad-trunk --grad-norm-every 50" ;;  # rung 2 (10-01): the alloc arm + the anchor HEAD-ONLY (ANCHOR_WEIGHT=0.1) + stop-grad at the trunk
    *) log "unknown arm $arm"; exit 1 ;;
  esac
  NAME=settings-$arm; LOOP=data/training/$NAME
  if [[ -f "$OUT/$arm.done" ]]; then log "cell $arm done already"; continue; fi
  if [[ ! -f "$LOOP/WALL-STOP" && ! -f "$LOOP/LOOP-COMPLETE" ]]; then
    log "cell $arm: loop (resumes from $LOOP/loop_state.json if present) extra='$EXTRA'"
    uv run python -m anvil.training.selfplay --name "$NAME" --ckpt "$CKPT" --iterations 200 --wall-hours "$WALL_HOURS" \
      --games 480 --games-per-pair 2 --workers "$WORKERS" --chunk 30 --port 50063 --seed-base 20260921 \
      --temperature 1.0 --replay 4 --fresh-weight 1.0 --replay-weight 0.33 --rl-workers 12 --epochs 1 --lr 1e-5 \
      --ent-weight 0.003 --ent-floor 0.08 --rl-seg 128 --guard-kl 0.06 --guard-ent-mult 2.0 --guard-veto-mult 1.5 \
      --guard-casts-floor 0.8 --penalty 0.02 --heur-frac 0.5 --value-weight 0.5 --traj-per-step 4 \
      --arms-every 5 --arms-pairs data/runs/d5arm-d0-s0-20260714-143546/pairs.txt --arms-games 200 --arms-seed-base 20260710 \
      --reask --jar "$JAR" --search-recipe "$FARGS" --search-alloc "$ALLOC" --search-floor 0.1 \
      --distill-carry-w --alloc-carry-w --state-bank "$BANK" --guard-spearman-floor 0.15 $EXTRA >> "$OUT/$arm.loop.log" 2>&1
    rc=$?
    if [[ -f "$LOOP/STOP" ]]; then log "cell $arm paused (STOP present) — exiting the chain; relaunch resumes"; exit 0; fi
    if [[ $rc -ne 0 && ! -f "$LOOP/WALL-STOP" ]]; then log "cell $arm loop FAILED rc=$rc"; exit 1; fi
    [[ -f "$LOOP/WALL-STOP" ]] || echo "$(date -Iseconds) iterations exhausted" > "$LOOP/LOOP-COMPLETE"
  fi
  FINAL=$(python3 -c "import json; print(json.load(open('$LOOP/loop_state.json'))['ckpt'])")
  ITERS=$(python3 -c "import json; print(json.load(open('$LOOP/loop_state.json'))['iteration'])")
  WALL=$(python3 -c "import json; print(round(json.load(open('$LOOP/loop_state.json')).get('wall_used_s',0)/3600,1))")
  if [[ ! -f "$OUT/$arm.read.done" ]]; then
    log "cell $arm: the 2,000-game read on $FINAL (network alone, $READ_GAMES / seat, $WORKERS x 2)"
    nice -n 19 uv run python scripts/final_read.py --ckpt "$FINAL" --name "sp-$arm" --games "$READ_GAMES" --workers "$WORKERS" \
      --port 50086 --servers 0 --jar "$JAR" --skip-ante >> "$OUT/$arm.read.log" 2>&1 || { log "cell $arm read FAILED"; exit 1; }
    ls -dt data/runs/sp-${arm}arm-s0-* | head -1 | tr -d '\n' > "$OUT/$arm.read.done"; echo -n "," >> "$OUT/$arm.read.done"; ls -dt data/runs/sp-${arm}arm-s1-* | head -1 >> "$OUT/$arm.read.done"
  fi
  READ=$(uv run python scripts/arms_report.py --arm "$arm=$(cat $OUT/$arm.read.done)" --out "$OUT/$arm.read.json" 2>/dev/null | grep -o "winrate [0-9.]* ± [0-9.]*" | head -1)
  LA=$(python3 -c "
import json,glob
fs=sorted(glob.glob('$LOOP/iter-*/arms-report.json'))
r=json.load(open(fs[-1])) if fs else {}
print(', '.join(f'{k} {v:.3f}' if isinstance(v,(int,float)) else f'{k} {v}' for k,v in r.items()) or 'n/a', fs[-1].split('/')[-2] if fs else '')" 2>/dev/null | cut -c1-120)
SR=$(python3 -c "
import json,glob
fs=sorted(glob.glob('$LOOP/iter-*/state-ranking.json'))
print(' / '.join(str(json.load(open(f)).get('spearman')) for f in fs) or 'n/a')" 2>/dev/null | cut -c1-160)
printf '| %s | %s | %s | %s | %s | %s | %s |\n' "$arm" "$WALL" "$ITERS" "$((ITERS*480))" "$FINAL" "$READ" "$LA" >> "$OUT/read.md"
printf '\nstate-ranking Spearman by iteration (%s): %s\n' "$arm" "$SR" >> "$OUT/read.md"
echo ok > "$OUT/$arm.done"; log "cell $arm CLOSED: $READ; spearman $SR"
done
log "settings-pass chain done"; echo OK > "$OUT/DONE"
