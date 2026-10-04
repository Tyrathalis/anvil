#!/usr/bin/env bash
# THE QUEUE AFTER THE CAST-MASK PAIRED READ (10-03 18:55, user): wait for after-recovery to leave the box,
# then THE NO-ANCHOR CONTROL — settings-pass arm `recovery-noanchor` = the recovery cell's flags minus
# --value-anchor (stop-grad at the trunk + --trunk-lr 3e-6 / --value-head-lr 1e-4), from the same
# shakedown-alloc/iter-019 (Spearman 0.250), the same 9 h wall, the same shuffle-mark jar, + the chain's
# 2,000-game read. Every anchored cell that held the Spearman also slowed the trunk, and the recipe of record
# carries both with gn_anchor = 0 on the trunk: the anchor term and the slow trunk are confounded.
# Pre-registered (running record 10-03 18:55): the same absolute bar as the recovery cell — the last
# iteration's Spearman ≥ 0.350 = the slow trunk alone holds the ranking → the Build 1 banks and the replay
# term leave the recipe (ADR-0118/0119 addendum); below, with the recovery cell above, = the anchor earns its
# place. The per-iteration tracks are read side by side (same start, same wall); the 2,000-game read is a
# strength point beside the recovery cell's, exploratory.
# Launch: uv run python -m anvil.runs launch --name after-paired --dir data/runs/after-paired \
#   --watch 'data/runs/after-recovery' --watch 'data/training/settings-recovery-noanchor' --watch 'data/runs/settings-pass6' \
#   --watch 'data/runs/sp*' --stall-min 240 --launched-by <session> -- bash scripts/after_paired_queue.sh
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/after-paired; mkdir -p "$OUT"
LAUNCHED_BY="${ANVIL_LAUNCHED_BY:-}"
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "waiting for after-recovery"
uv run python -m anvil.runs wait --name after-recovery >> "$OUT/queue.log" 2>&1; log "after-recovery left: $(grep -o '"state": "[a-z]*"' ~/.local/state/anvil/runs/after-recovery.json)"
sleep 30
log "the no-anchor control: settings-pass chain, arm recovery-noanchor, from shakedown-alloc/iter-019, 9 h, the shuffle-mark jar"
CHAIN_OUT=settings-pass6 ARMS=recovery-noanchor WALL_HOURS=9 \
  CKPT=data/training/shakedown-alloc/iter-019/train/last.pt JAR=$REPO/data/runs/shufflemark/forge-shufflemark.jar \
  uv run python -m anvil.runs launch --name settings-pass6 --dir "$REPO/data/runs/settings-pass6" \
  --watch 'data/training/settings-recovery-noanchor' --watch 'data/runs/sp*' --stall-min 180 \
  ${LAUNCHED_BY:+--launched-by "$LAUNCHED_BY"} \
  -- bash scripts/settings_pass_chain.sh >> "$OUT/queue.log" 2>&1
log "launched settings-pass6"; echo OK > "$OUT/DONE"
