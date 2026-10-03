#!/usr/bin/env bash
# THE QUEUE AFTER THE ANTE RE-MEASURE (10-03, user): wait for ante-remeasure to leave the box, then
# launch THE DRIFTED-TRUNK RECOVERY READ (ADR-0119 addendum 10-03: "a short continuation from
# shakedown-alloc/iter-019 under this recipe decides the big run's warm start") as a settings-pass cell:
# arm `recovery` = the rung-2 recipe (head-only anchor 0.1 + --value-stopgrad-trunk + trunk-lr 3e-6 /
# value-head-lr 1e-4) warm-started from shakedown-alloc/iter-019 (Spearman 0.250 ± 0.029), WALL_HOURS 9
# (≈ 6 iterations at the alloc cadence) + the chain's 2,000-game read, on the shuffle-mark jar (the pin).
# Pre-registered (running record 10-03): the Spearman at the cell's last iteration ≥ 0.350 (within one
# bootstrap SE of day-zero 0.374, ADR-0118's letter) = the drifted trunk RECOVERS → the big run may
# warm-start from iter-019; below = day-zero is the warm start. The 2,000-game read is a strength point
# beside alloc's 0.5405 ± 0.0111, exploratory (a −2 SE gap flags).
# Launch: uv run python -m anvil.runs launch --name after-remeasure --dir data/runs/after-remeasure \
#   --watch 'data/runs/ante-remeasure' --watch 'data/forkcheck/run-20261003-castmask' --watch 'data/training/settings-recovery' --watch 'data/runs/settings-pass5' \
#   --watch 'data/runs/sp*' --stall-min 240 -- bash scripts/after_remeasure_queue.sh
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/after-remeasure; mkdir -p "$OUT"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "waiting for ante-remeasure"
uv run python -m anvil.runs wait --name ante-remeasure >> "$OUT/queue.log" 2>&1; log "ante-remeasure left: $(grep -o '"state": "[a-z]*"' ~/.local/state/anvil/runs/ante-remeasure.json)"
sleep 30
# 0. (10-03 15:50) the cast-mask forkcheck first — the option scan now runs the realizer's cast-restrictions
#    clause (fork branch cast-mask; the Spider-Man 2099 fix); a serve / recording-path change, so the 500
#    main-trace hashes must match the baseline. ≈ 30 min on the quiet box, before the recovery cell's wall
#    budget starts (the forkcheck is held out of every equal-box-time cell).
FC=$REPO/data/forkcheck/run-20261003-castmask
if [[ ! -f "$FC/compare.txt" ]]; then
  log "0. the cast-mask forkcheck ($(head -c 40 $REPO/data/runs/castmask/JAR.txt))"
  N_GAMES=500 SEED=20260703 JAR=$REPO/data/runs/castmask/forge-castmask.jar FORGE_DIR=$HOME/Everything/Projects/forge-castmask \
    bash scripts/forkcheck/run_forkcheck.sh "$FC" | tee -a "$OUT/queue.log"
  FC_PID=$(cat "$FC/run.pid")
  until [ ! -d /proc/$FC_PID ] || { [ -f "$FC/results.jsonl" ] && [ "$(wc -l < "$FC/results.jsonl")" -ge 500 ]; }; do sleep 60; done
  uv run python scripts/forkcheck/compare.py "$FC" | tee "$FC/compare.txt" | tee -a "$OUT/queue.log"
  log "cast-mask forkcheck: $(grep -i "identical" "$FC/compare.txt" | head -1)"
fi
log "the recovery read: settings-pass chain, arm recovery, from shakedown-alloc/iter-019, 9 h, the shuffle-mark jar"
CHAIN_OUT=settings-pass5 ARMS=recovery WALL_HOURS=9 ANCHOR_WEIGHT=0.1 \
  CKPT=data/training/shakedown-alloc/iter-019/train/last.pt JAR=$REPO/data/runs/shufflemark/forge-shufflemark.jar \
  uv run python -m anvil.runs launch --name settings-pass5 --dir "$REPO/data/runs/settings-pass5" \
  --watch 'data/training/settings-recovery' --watch 'data/runs/sp*' --stall-min 180 \
  -- bash scripts/settings_pass_chain.sh >> "$OUT/queue.log" 2>&1
log "launched settings-pass5"; echo OK > "$OUT/DONE"
