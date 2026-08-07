"""Mid-campaign probe checkpoint (M6 pre-tranche item, ADR-0044 rider).

The label tranche exists to feed the B-2 unfreeze lever, whose label curve
was rising at the 3.6K boundary (1K 0.443 -> 2K 0.450 -> 3.6K 0.4769,
ADR-0044). This checkpoint extends that curve MID-CAMPAIGN: at a phase
boundary (fresh stores ingested, ~2-3K new labels banked), it merges the
interim labels train-side, banks examples for the new positions, runs the
N=2 lr=3e-5 cell at 2 seeds on the same frozen holdout, and notifies with
the new curve point — so a flattening curve stops a 2-day campaign after
half a day.

Pre-registered decision rule (exit code drives the campaign script):
  mean holdout Spearman >= CONTINUE_AT (0.478 = the 3.6K point + ~2
  seed-sds)                -> exit 0 (curve still rising, continue)
  otherwise                -> exit 2 (flat/regressing — campaign pauses,
                              user decides; everything is resumable)

The unfreeze probe itself never reads v_era/v_d4, so interim rows skip the
trace join entirely (traces happen once, post-campaign, in the real
label_merge). Freeze discipline: interim rows hashing into the holdout are
dropped (the label_merge belt, applied early); the eval side is the frozen
ext2-c2 holdout, byte-identical.

Usage (called by the campaign script between phases; standalone fine too):
  uv run python scripts/tranche_checkpoint.py \
      --labels data/runs/<map-or-arm-dir> [--labels ...] \
      --bank data/runs/unfreeze-probe-v1/examples.pt \
      --out data/runs/<campaign-dir>/checkpoint-1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frozen_probe as fp  # noqa: E402
import unfreeze_probe as up  # noqa: E402
from label_merge import held_out  # noqa: E402

BASE_DATASET = "data/runs/frozen-probe-ext2-c2/dataset.jsonl"
CONTINUE_AT = 0.478  # 3.6K point 0.4769 + ~2 seed-sds (ADR-0044)
POINT_3K6 = 0.4769


def interim_rows(label_dirs: list[str], era: str) -> tuple[list[dict], dict]:
    rows, dropped_ho, dupes = [], 0, 0
    for src in label_dirs:
        seen: set = set()
        path = Path(src, "drills.jsonl")
        if not path.exists():
            continue
        for line in path.open():
            r = json.loads(line)
            if r["n"] <= 0:
                continue
            key = (r["store"], r["g"], r["fired_t"])
            if key in seen:
                dupes += 1
                continue
            seen.add(key)
            if held_out(r["store"], r["g"]):
                dropped_ho += 1
                continue
            rows.append({"era": era, "src": Path(src).name,
                         "store": r["store"], "g": r["g"], "t": r["fired_t"],
                         "wr": r["model_wins"] / r["n"], "n": r["n"]})
    return rows, {"holdout_hash_dropped": dropped_ho, "crash_dupes": dupes}


def main() -> None:
    import torch

    from anvil.ante.ledger import ValueEvaluator

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--labels", action="append", required=True)
    ap.add_argument("--bank", default="data/runs/unfreeze-probe-v1/examples.pt")
    ap.add_argument("--base", default=BASE_DATASET)
    ap.add_argument("--era", default="c2")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seeds", default="0,1")
    ap.add_argument("--continue-at", type=float, default=CONTINUE_AT)
    a = ap.parse_args()
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    base = [r for r in fp.load_rows(a.base) if r["era"] == a.era]
    fresh, stats = interim_rows(a.labels, a.era)
    base_keys = {(r["store"], r["g"], r["t"], r["src"]) for r in base}
    fresh = [r for r in fresh
             if (r["store"], r["g"], r["t"], r["src"]) not in base_keys]
    rows = base + fresh
    print(f"[ckpt] {len(base)} base + {len(fresh)} fresh train labels "
          f"({stats}); running the N=2 cell at seeds {a.seeds}")

    bank = torch.load(a.bank, weights_only=False)
    keys, examples = list(bank["keys"]), list(bank["examples"])
    have = set(keys)
    need = sorted({(r["store"], r["g"], r["t"]) for r in fresh
                   if f"{r['store']}:{r['g']}:{r['t']}" not in have})
    if need:
        t0 = time.time()
        ev = ValueEvaluator(up.CKPT)
        nk, nx = up.collect_examples(need, ev)
        keys += nk
        examples += nx
        torch.save({"keys": keys, "examples": examples, "ckpt": up.CKPT,
                    "dataset": f"{a.base}+interim"},
                   out_dir / "examples-interim.pt")
        print(f"[ckpt] banked {len(nk)} new examples in "
              f"{time.time() - t0:.0f}s")
        del ev
        torch.cuda.empty_cache()

    key_idx = {k: i for i, k in enumerate(keys)}
    row_idx = np.array([key_idx[f"{r['store']}:{r['g']}:{r['t']}"]
                        for r in rows])
    y = np.array([r["wr"] for r in rows])
    games = np.array([f"{r['store']}:{r['g']}" for r in rows])
    ho = np.array([fp._held_out(r["store"], r["g"]) for r in rows])
    assert not any(ho[len(base):]), "fresh rows must be train-side only"

    cells = []
    for seed in [int(s) for s in a.seeds.split(",")]:
        cell_args = SimpleNamespace(seed=seed, batch=192, max_epochs=200,
                                    patience=15, train_size=None)
        cells.append({**up._cell(2, 3e-5, examples, row_idx, y, games, ho,
                                 cell_args), "seed": seed})
    mean_s = float(np.mean([c["holdout_spearman"] for c in cells]))
    go = mean_s >= a.continue_at
    report = {
        "n_train_labels": int((~ho).sum()), "n_fresh": len(fresh),
        "n_holdout": int(ho.sum()), "interim_stats": stats,
        "cells": cells, "mean_holdout_spearman": round(mean_s, 4),
        "reference_3k6_point": POINT_3K6, "continue_at": a.continue_at,
        "verdict": "CONTINUE (curve rising)" if go
                   else "PAUSE (curve flat/regressing — user decides)"}
    (out_dir / "checkpoint-report.json").write_text(
        json.dumps(report, indent=2) + "\n")
    print(f"[ckpt] curve point: {int((~ho).sum())} train labels -> "
          f"{mean_s:.4f} (3.6K point {POINT_3K6}, continue-at "
          f"{a.continue_at}) => {report['verdict']}")
    try:
        from anvil.training.notify import notify
        notify("tranche checkpoint",
               f"{int((~ho).sum())} labels -> {mean_s:.4f} "
               f"(vs {POINT_3K6} @3.6K) => {report['verdict']}")
    except Exception:
        pass
    sys.exit(0 if go else 2)


if __name__ == "__main__":
    main()
