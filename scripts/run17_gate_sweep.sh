#!/usr/bin/env bash
# run17 two-candidate gate sweep (user-approved 2026-08-18): the standing
# combined paired read on the two leading ckpts of the M8 D2'
# critic-ordered curation run — iter-009 (the peak arms read, 0.5575 ±
# 0.0248) then iter-010 (the last accepted ckpt before the iteration-11
# veto-guard halt at 0.3032 > 1.5x iter-0). ARMS-SELECTED mid-run ckpts
# (M6 two-leading precedent; selection disclosed in the M8 closeout ADR;
# the gate threshold is untouched). Sequential: calibrated measurements
# do not share the fleet.
# Gate: 0.5373 ± 0.0112 on era d798917ae5 (ADR-0055).
set -euo pipefail
cd "$(dirname "$0")/.."
uv run python scripts/final_read.py \
  --ckpt data/training/d6-run17/iter-009/train/last.pt \
  --name run17-i009-final
uv run python scripts/final_read.py \
  --ckpt data/training/d6-run17/iter-010/train/last.pt \
  --name run17-i010-final
