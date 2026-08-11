"""Sequence-probe read (M7 D2 routing pin, 2026-08-11).

Consumes -forceseq labels JSONL (one row per fork point, three arms:
w_nat[]/w_hold[]/w_act[] over paired triples) and reports, for each
pairwise contrast (hold-nat, act-nat, act-hold):

  - coverage: fork points, seat_skips, triples achieved vs K, per-arm
    crash counts, act-arm exhaust rate (windows degraded to pass)
  - per-point paired dwr for the drilled seat (draws count as non-wins,
    symmetric across arms)
  - the ADR-0051/0052 variance decomposition: SD of point dwr vs the
    independent binomial floor; var_signal = var_obs - mean paired
    binomial var; RMS true dwr — the probe's deliverable is whether ANY
    contrast shows resolvable sequence-level signal where the
    single-decision read (ADR-0052) was null

Usage:
  python scripts/seq_probe_read.py <labels.jsonl> [...] [--seat-index 0]
"""
from __future__ import annotations

import argparse
import json
import math
import sys


def load(paths: list[str]) -> list[dict]:
    rows = []
    for p in paths:
        for line in open(p):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("seq"):
                rows.append(r)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("labels", nargs="+")
    ap.add_argument("--seat-index", type=int, default=0,
                    help="drilled seat's index into the w_* arrays")
    a = ap.parse_args()

    rows = load(a.labels)
    if not rows:
        sys.exit("no seq rows found")

    skips = [r for r in rows if r.get("seat_skip")]
    pts = [r for r in rows if not r.get("seat_skip")]
    n_hor = sorted({r.get("n") for r in pts})
    print(f"fork points: {len(rows)} total, {len(skips)} seat_skip, "
          f"{len(pts)} probed (horizon n={n_hor})")
    tot_triples = sum(r["triples"] for r in pts)
    tot_k = sum(r["k"] for r in pts)
    crash = [sum(r.get(f"crash_{arm}", 0) for r in pts)
             for arm in ("nat", "hold", "act")]
    print(f"triples {tot_triples}/{tot_k} ({tot_triples / max(1, tot_k):.1%}), "
          f"crashes nat/hold/act {crash}, holds {sum(r.get('holds', 0) for r in pts)}, "
          f"forced casts {sum(r.get('acts', 0) for r in pts)}, "
          f"act exhausts {sum(r.get('exhausts', 0) for r in pts)}, "
          f"nat anomalies {sum(r.get('nat_anom', 0) for r in pts)}")

    si = a.seat_index
    usable = [r for r in pts if r["triples"] >= 2]
    print(f"usable (>=2 triples): {len(usable)}")
    for hi, lo, label in (("hold", "nat", "hold - nat"),
                          ("act", "nat", "act  - nat"),
                          ("act", "hold", "act  - hold")):
        dwrs, binvars = [], []
        for r in usable:
            n = r["triples"]
            wh = r[f"w_{hi}"][si] / n
            wl = r[f"w_{lo}"][si] / n
            dwrs.append(wh - wl)
            binvars.append((wh * (1 - wh) + wl * (1 - wl)) / n)
        m = sum(dwrs) / len(dwrs)
        var_obs = sum((d - m) ** 2 for d in dwrs) / max(1, len(dwrs) - 1)
        mean_bin = sum(binvars) / len(binvars)
        var_sig = max(0.0, var_obs - mean_bin)
        neg = sum(1 for d in dwrs if d < 0)
        pos = sum(1 for d in dwrs if d > 0)
        print(f"\n{label}: mean dwr {m:+.4f} | SD(point) {math.sqrt(var_obs):.4f} "
              f"| indep floor {math.sqrt(mean_bin):.4f}")
        print(f"  var_signal {var_sig:.5f} -> RMS true dwr {math.sqrt(var_sig):.4f} "
              f"| direction: {pos} pos / {neg} neg / {len(dwrs) - pos - neg} zero")


if __name__ == "__main__":
    main()
