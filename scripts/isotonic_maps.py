"""Era-scoped isotonic map export (M6 D4 rider, ADR-0036 adoption).

ADR-0036 adopted isotonic remaps as era-scoped assets (they fix absolute
calibration: ECE 0.33 -> 0.03), but the fits only ever lived inside
critic_calibration.py's evaluation — report.json holds metrics, not the
map. This tool persists the maps so curation/doom tooling can consume
calibrated values by default (m6-plan D4: "lands before any new curation
runs").

Fit basis: ALL labels of the given dataset per (era, critic) — an asset
map wants every label, unlike the report's held-out evaluation split. The
label set is the standing value-audit set and GROWS with every map/sweep
(ADR-0036 decision); re-export after each growth, bump the version.

Era discipline: a map is valid ONLY for values produced by its era's
critic on its era's policy distribution (rollout truth is
policy-conditional). Consumers must pick the key matching their ckpt:
`c2/v_era` = the iter-019 on-policy critic, `c2/v_d4` = d4-critic-fullvis
on c2-era games, etc.

Usage:
  uv run python scripts/isotonic_maps.py export \
      --dataset data/runs/frozen-probe-ext2-c2/dataset.jsonl \
      --out data/runs/isotonic-maps/isotonic-maps-v1.json
  uv run python scripts/isotonic_maps.py inspect \
      --maps data/runs/isotonic-maps/isotonic-maps-v1.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from critic_calibration import ece, pav_apply, pav_fit  # noqa: E402

CRITICS = ("v_era", "v_d4")


def load_map(path: str | Path, key: str):
    """-> (lo, vals) arrays for pav_apply; raises KeyError on a missing
    era/critic key (loud — a wrong-era map is silent miscalibration)."""
    doc = json.loads(Path(path).read_text())
    m = doc["maps"][key]
    return np.array(m["lo"]), np.array(m["vals"])


def export(args: argparse.Namespace) -> None:
    rows = [json.loads(line) for line in Path(args.dataset).open()]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    maps: dict = {}
    for era in sorted({r["era"] for r in rows}):
        er = [r for r in rows if r["era"] == era]
        y = np.array([r["wr"] for r in er])
        for ck in CRITICS:
            v = np.array([r[ck] for r in er])
            lo, vals = pav_fit(v, y)
            remapped = pav_apply(v, lo, vals)
            maps[f"{era}/{ck}"] = {
                "lo": [round(float(x), 6) for x in lo],
                "vals": [round(float(x), 6) for x in vals],
                "n_labels": len(er), "n_steps": len(vals),
                "ece_raw": round(ece(v, y), 4),
                "ece_remapped": round(ece(remapped, y), 4)}
            print(f"[maps] {era}/{ck}: {len(er)} labels -> {len(vals)} steps, "
                  f"ECE {maps[f'{era}/{ck}']['ece_raw']:.4f} -> "
                  f"{maps[f'{era}/{ck}']['ece_remapped']:.4f}")
    doc = {"provenance": {
        "dataset": str(args.dataset),
        "created": _dt.date.today().isoformat(),
        "fit": "PAV on ALL labels (asset map; report-style holdout lives "
               "in critic_calibration.py)",
        "era_scope": "a map is valid only for its era's critic values "
                     "(ADR-0036: rollout truth is policy-conditional)"},
        "maps": maps}
    out.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"[maps] -> {out}")


def inspect(args: argparse.Namespace) -> None:
    doc = json.loads(Path(args.maps).read_text())
    print(json.dumps(doc["provenance"], indent=2))
    for k, m in doc["maps"].items():
        grid = np.linspace(0.05, 0.95, 10)
        remap = pav_apply(grid, np.array(m["lo"]), np.array(m["vals"]))
        pairs = " ".join(f"{a:.2f}->{b:.2f}" for a, b in zip(grid, remap))
        print(f"{k} (n={m['n_labels']}, ECE {m['ece_raw']}->"
              f"{m['ece_remapped']}): {pairs}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("export")
    p.add_argument("--dataset",
                   default="data/runs/frozen-probe-ext2-c2/dataset.jsonl")
    p.add_argument("--out",
                   default="data/runs/isotonic-maps/isotonic-maps-v1.json")
    p.set_defaults(fn=export)
    p = sub.add_parser("inspect")
    p.add_argument("--maps",
                   default="data/runs/isotonic-maps/isotonic-maps-v1.json")
    p.set_defaults(fn=inspect)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
