#!/usr/bin/env bash
# M8 D1 natural-timing probe (m8-plan D1, gate PINNED 2026-08-17 before
# generation): single NATURAL arm under an OBSERVE directive, K=64, the 99
# model-active in-band points (drill-selection-v5-active), N=4 recorded for
# bin comparability only (no directive runs). Era jar d798917ae5 + the
# labels-only extension (boundary-exemption proof: data/forkcheck/m8d1-proof,
# era-vs-ext FIXED_HASH 500-game pair). Mirrors the M7 campaign invocation:
# argmax mainline replay on the source ckpt, fork completions sampled by the
# SAME iter-019 via --fork-instrument. ~6,300 completions ≈ 2h at w=16.
# Read: scripts/natural_timing_read.py data/runs/drillm8d1nat-*/workers/inv-*/labels.jsonl
set -euo pipefail
cd "$(dirname "$0")/.."
export DISPLAY="${DISPLAY:-:0}"
if [[ -z "${XAUTHORITY:-}" ]]; then
  for f in /run/user/1000/xauth_*; do export XAUTHORITY="$f"; break; done
fi
exec uv run python -m anvil.grindstone generate \
  --manifest data/runs/m8d1-natprobe-plan \
  --port 50063 --workers 16 \
  --force-seq 4 --seq-arms nat \
  --drill-ckpt data/training/d6-run11/iter-019/train/last.pt
