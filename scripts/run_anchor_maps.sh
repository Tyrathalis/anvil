#!/usr/bin/env bash
# Three-anchor drill-map chain (the cycle protocol, post-ADR-0052):
# plan + generate + report at crash-2 / crash-4 / peak, K completions per
# point, one arm at a time (each generate owns the GPU server serially).
# Mainline serving: argmax by default (correct for argmax sources like
# final_read arms); pass --sample-mainline as an extra flag for
# sampled-source curation (ADR-0052 requirement).
#
# Usage:
#   TAG=d3 scripts/run_anchor_maps.sh <curation.jsonl> <replay-ckpt> \
#       <out-base> <K> [extra generate flags...]
#
# Resume-safe: arms with REPORT_DONE skip; a crashed generate re-runs and
# report aggregates every run dir (later runs supersede per game).
set -euo pipefail
cd "$(dirname "$0")/.."
CUR=$1; CK=$2; OUT=$3; K=$4; shift 4
TAG=${TAG:-map}
export PYTHONUNBUFFERED=1

for spec in "o2 crash -2" "o4 crash -4" "pk peak 0"; do
  read -r name anchor off <<<"$spec"
  arm="$OUT/arm-$name"
  if [ -f "$arm/REPORT_DONE" ]; then
    echo "[maps] $arm already reported, skipping"
    continue
  fi
  uv run python -m anvil.grindstone plan --curation "$CUR" --out "$arm" \
      --ckpt "$CK" --k "$K" --anchor "$anchor" --turn-offset "$off" \
      --tag "$TAG$name"
  uv run python -m anvil.grindstone generate --manifest "$arm" \
      --port "${PORT:-50067}" --workers "${WORKERS:-16}" "$@"
  uv run python -m anvil.grindstone report --manifest "$arm"
  touch "$arm/REPORT_DONE"
done
touch "$OUT/DONE"
uv run python -c "from anvil.training.notify import notify; import sys; \
notify('anvil drill-maps', 'three-anchor chain COMPLETE: ' + sys.argv[1], tag='maps')" "$OUT"
