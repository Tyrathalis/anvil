#!/usr/bin/env bash
# run16 two-candidate gate sweep (user-approved 2026-08-16): the standing
# combined paired read on the two arms-leading ckpts, iter-014 then
# iter-009 (M6 two-leading precedent; ARMS-SELECTED mid-run ckpts — the
# selection is disclosed in the M7 closeout ADR; the gate threshold is
# untouched). Sequential: calibrated measurements do not share the fleet.
# Gate: 0.5373 ± 0.0112 on era d798917ae5 (ADR-0055).
set -euo pipefail
cd "$(dirname "$0")/.."
uv run python scripts/final_read.py \
  --ckpt data/training/d6-run16/iter-014/train/last.pt \
  --name run16-i014-final
uv run python scripts/final_read.py \
  --ckpt data/training/d6-run16/iter-009/train/last.pt \
  --name run16-i009-final
