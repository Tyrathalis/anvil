"""Selection composition adjuster (M6 cycle-3, the D3 fold-in).

`grindstone select` fixes the winrate band but not the anchor mix; the
a2-winning composition (ADR-0031) carried 18.8% ahead-anchored
positions. This step swaps crash-anchored entries to their game's
peak-anchored drill point (where the peak arm labeled it inside the
band) in deterministic hash order until the ahead share hits target.
Total list size unchanged; every swap stays band-eligible.

Usage:
  uv run python scripts/compose_selection.py \
      --selection data/runs/drill-selection-v4 \
      --peak-arm data/runs/drill-sweep-cycle3/arm-peak \
      --ahead-share 0.188
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selection", required=True)
    ap.add_argument("--peak-arm", required=True)
    ap.add_argument("--ahead-share", type=float, default=0.188)
    ap.add_argument("--band", default="0.25:0.85")
    a = ap.parse_args()
    lo, hi = (float(x) for x in a.band.split(":"))

    sel_dir = Path(a.selection)
    rows = [json.loads(x) for x in (sel_dir / "selection.jsonl").read_text().splitlines()]
    peak = {}
    for x in (Path(a.peak_arm) / "drills.jsonl").read_text().splitlines():
        r = json.loads(x)
        if r["n"] > 0:
            peak[(r["store"], r["g"])] = r

    def is_ahead(r: dict) -> bool:
        return r["drill_turn"] == r["peak_turn"] and r["peak_turn"] < r["crash_from_turn"]

    n = len(rows)
    target = round(a.ahead_share * n)
    have = sum(1 for r in rows if is_ahead(r))
    # crash-anchored entries whose game has a band-eligible peak label,
    # deterministic hash order
    cands = [
        r
        for r in rows
        if not is_ahead(r)
        and r["drill_turn"] == r["crash_from_turn"]
        and (r["store"], r["g"]) in peak
    ]
    cands = [
        r
        for r in cands
        if lo <= (lambda p: p["model_wins"] / p["n"])(peak[(r["store"], r["g"])]) <= hi
        and peak[(r["store"], r["g"])]["fired_t"] < r["crash_from_turn"]
    ]
    cands.sort(key=lambda r: hashlib.sha256(f"compose:{r['store']}:{r['g']}".encode()).hexdigest())
    swapped = 0
    for r in cands:
        if have + swapped >= target:
            break
        p = peak[(r["store"], r["g"])]
        r["drill_turn"] = p["fired_t"]
        r["sel_wr"] = p["model_wins"] / p["n"]
        r["sel_n"] = p["n"]
        r["sel_rule"] = "band-peak-compose"
        swapped += 1

    (sel_dir / "selection.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    meta = json.loads((sel_dir / "meta.json").read_text())
    final = sum(1 for r in rows if is_ahead(r))
    meta["compose"] = {
        "ahead_target": a.ahead_share,
        "swapped": swapped,
        "ahead_share": round(final / n, 4),
        "mean_sel_wr": round(sum(r["sel_wr"] for r in rows) / n, 4),
    }
    (sel_dir / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(
        f"[compose] {swapped} swaps -> ahead {final}/{n} = {final / n:.1%} "
        f"(target {a.ahead_share:.1%}), mean wr "
        f"{meta['compose']['mean_sel_wr']}"
    )


if __name__ == "__main__":
    main()
