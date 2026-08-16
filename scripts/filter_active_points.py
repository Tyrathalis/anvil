"""Filter a drill selection to model-seat-ACTIVE points (ADR-0054 campaign
selection rule) using a cheap forced-seq screening pass (K=1, N=1).

A campaign point only yields labels when the fork window's priority player
is the drilled/bridge seat; the smoke measured a 35% activity rate on an
unfiltered selection (13/20 seat_skips), so an unscreened campaign wastes
~2/3 of its mainline replays. Screening: run the campaign machinery at
K=1/N=1 over the full selection (one triple per point, ~15 min), then keep
the selection rows whose labels row is not seat_skip.

Usage:
  uv run python scripts/filter_active_points.py \
      --selection data/runs/drill-selection-v5/selection.jsonl \
      --screening data/runs/drillscr-*  \
      --out data/runs/drill-selection-v5-active
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selection", required=True)
    ap.add_argument("--screening", nargs="+", help="screening run dirs (globs ok)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    active: set[tuple[str, int, int]] = set()
    skipped = other = 0
    for pat in a.screening:
        for rd in glob.glob(pat):
            run = json.loads((Path(rd) / "run.json").read_text())
            # the arm's source store name identifies which selection rows it
            # screened; labels i = source game index, t = fork turn
            src = Path(run["drill_source"]).stem if run.get("drill_source") else None
            store = run["pairs_source"].split("/")[-2] if run.get("pairs_source") else src
            for f in Path(rd).glob("workers/inv-*/labels.jsonl"):
                for line in open(f):
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not r.get("seq"):
                        continue
                    if r.get("seat_skip"):
                        skipped += 1
                        continue
                    if not r.get("triples"):
                        other += 1
                        continue
                    active.add((store, r["i"], r["t"]))

    rows = [json.loads(x) for x in open(a.selection)]
    kept = []
    for row in rows:
        store = row.get("store", "")
        if any(k[1] == row["g"] and k[2] == row.get("drill_turn") and k[0] in store for k in active):
            kept.append(row)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "selection.jsonl").write_text("".join(json.dumps(r) + "\n" for r in kept))
    (out / "meta.json").write_text(
        json.dumps(
            {
                "source_selection": a.selection,
                "screening": a.screening,
                "in": len(rows),
                "active": len(kept),
                "seat_skips": skipped,
                "other_skips": other,
            },
            indent=1,
        )
        + "\n"
    )
    print(
        f"[filter] {len(rows)} -> {len(kept)} active points "
        f"({skipped} seat_skips, {other} other) -> {out}/selection.jsonl"
    )


if __name__ == "__main__":
    main()
