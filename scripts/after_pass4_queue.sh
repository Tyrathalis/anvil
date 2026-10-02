#!/usr/bin/env bash
# THE QUEUE AFTER THE RUNG 2 RERUN (10-02, user): wait for settings-pass4 to leave the box, then
#   1. the rung 2 margin read (scripts/margin_read_chain.sh, ARM=stopgrad-t3e6) — only if the cell closed
#      normally (its DONE); a halt / failure gets a human, not a read;
#   2. merge the baseline-reads branch (worktree-bridge-cse_019NKHnNvxzKtQy4uFypPRk1: final_read
#      --seat-forge-args, scripts/baseline_reads*.{py,sh}, the Discord survey) into main — conflict-free
#      against main at cce6b4f (merge-tree checked 10-02 07:10); deferred to here because final_read.py is
#      the running cell's read driver;
#   3. launch the baseline reads (scripts/baseline_reads_chain.sh: the jar build from ../forge-baselines
#      first, then randheur / modelrand / heur / heursearch + the three cost probes; ≈ 5–6 h + ≤ 9 h).
# Launch: uv run python -m anvil.runs launch --name after-pass4 --dir data/runs/after-pass4 \
#   --watch 'data/training/settings-stopgrad-t3e6' --watch 'data/runs/settings-pass4' --watch 'data/runs/rung2-margin-read' \
#   --watch 'data/runs/rr-*' --watch 'data/runs/baseline-reads' --watch 'data/runs/br-*' --stall-min 240 \
#   -- bash scripts/after_pass4_queue.sh
set -u
REPO=/home/tyrathalis/Everything/Projects/Anvil; cd "$REPO"
OUT=$REPO/data/runs/after-pass4; mkdir -p "$OUT"
BRANCH=worktree-bridge-cse_019NKHnNvxzKtQy4uFypPRk1
log() { echo "$(date -Iseconds) $*" | tee -a "$OUT/queue.log"; }
log "waiting for settings-pass4"
uv run python -m anvil.runs wait --name settings-pass4 >> "$OUT/queue.log" 2>&1; log "settings-pass4 left: $(grep -o '"state": "[a-z]*"' ~/.local/state/anvil/runs/settings-pass4.json)"
sleep 30
if [[ -f data/runs/settings-pass4/DONE ]]; then
  if [[ ! -f data/runs/rung2-margin-read/DONE ]]; then
    log "1. the rung 2 margin read"
    ARM=stopgrad-t3e6 uv run python -m anvil.runs launch --name rung2-margin-read --dir "$REPO/data/runs/rung2-margin-read" \
      --watch 'data/runs/rr-*' --stall-min 60 -- bash scripts/margin_read_chain.sh >> "$OUT/queue.log" 2>&1
    uv run python -m anvil.runs wait --name rung2-margin-read >> "$OUT/queue.log" 2>&1
    log "margin read: $(tail -1 data/runs/rung2-margin-read/read.md 2>/dev/null)"
  fi
else
  log "settings-pass4 did not close normally (no DONE) — the margin read is skipped; a human reads the halt"
fi
log "2. merging $BRANCH into main"
if [[ -n "$(git status --short)" ]]; then log "main is dirty — not merging; the baseline reads need the branch"; exit 1; fi
git merge --no-edit "$BRANCH" >> "$OUT/queue.log" 2>&1 || { log "merge FAILED"; exit 1; }
log "main at $(git rev-parse --short HEAD)"
log "3. the baseline reads"
uv run python -m anvil.runs launch --name baseline-reads --dir "$REPO/data/runs/baseline-reads" \
  --watch 'data/runs/br-*' --stall-min 90 -- bash scripts/baseline_reads_chain.sh >> "$OUT/queue.log" 2>&1
uv run python -m anvil.runs wait --name baseline-reads >> "$OUT/queue.log" 2>&1
log "baseline reads left: $(grep -o '"state": "[a-z]*"' ~/.local/state/anvil/runs/baseline-reads.json); $(tail -1 data/runs/baseline-reads/queue.log 2>/dev/null | cut -c1-300)"
echo OK > "$OUT/DONE"
