"""Forced-branch paired-rollout read (M7 D2, m7-plan pin 7).

Consumes -forcebranch labels JSONL (one row per fork point, both branches:
w_act[]/w_hold[] over paired completions) and reports, per K and overall:

  - coverage: fork points, seat_skips, pairs achieved vs K, skip_act rate
    (the pin-5 finding: high skip = drilled decisions are hold-only states)
  - per-point paired dwr = wr_act - wr_hold for the drilled seat (draws in
    the denominator, i.e. counted as non-wins for both branches — symmetric,
    cancels in the difference's expectation)
  - the paired SE of dwr vs K: empirical SD of per-point dwr, plus the
    binomial floor 	sqrt(2 * p(1-p) / K) for reference — the sizing read's
    deliverable is where the empirical paired SE sits below that floor
    (pairing works) and how it scales with K
  - signal decomposition (ADR-0051's estimator): var_signal =
    var_observed - mean(paired binomial var); RMS true dwr

Usage:
  python scripts/forced_branch_read.py <labels.jsonl> [<labels2.jsonl> ...]
      [--seat-index 0]

Seat index: which registered player is the drilled seat in w_* arrays
(harness convention: -bridgeseats 0 => model is seat 0 in -d order; pairs
files map seats per game — pass per-file overrides if a run mixes).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter


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
                continue  # torn tail line
            if r.get("forced"):
                rows.append(r)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("labels", nargs="+")
    ap.add_argument("--seat-index", type=int, default=0,
                    help="drilled seat's index into w_act/w_hold")
    a = ap.parse_args()

    rows = load(a.labels)
    if not rows:
        sys.exit("no forced rows found")

    seat_skips = [r for r in rows if r.get("seat_skip")]
    pts = [r for r in rows if not r.get("seat_skip")]
    print(f"fork points: {len(rows)} total, {len(seat_skips)} seat_skip, "
          f"{len(pts)} forced")

    skid = Counter()
    for r in pts:
        for k, v in (r.get("skips") or {}).items():
            skid[k] += v
    if skid:
        print("skip reasons:", dict(skid))

    si = a.seat_index
    by_k: dict[int, list[dict]] = {}
    for r in pts:
        by_k.setdefault(r["k"], []).append(r)

    for K in sorted(by_k):
        grp = by_k[K]
        total_pairs = sum(r["pairs"] for r in grp)
        total_skip = sum(r.get("skip_act", 0) for r in grp)
        total_crash = sum(r.get("crash_act", 0) + r.get("crash_hold", 0)
                          for r in grp)
        usable = [r for r in grp if r["pairs"] >= 2]
        print(f"\nK={K}: {len(grp)} points, pairs {total_pairs}/{len(grp) * K} "
              f"({total_pairs / (len(grp) * K):.1%}), skip_act {total_skip}, "
              f"crashes {total_crash}, usable(>=2 pairs) {len(usable)}")
        if not usable:
            continue
        dwrs, binvars = [], []
        for r in usable:
            n = r["pairs"]
            wa, wh = r["w_act"][si] / n, r["w_hold"][si] / n
            dwrs.append(wa - wh)
            # paired binomial var of the difference at this point (upper
            # bound: independent branches; pairing can only shrink it)
            binvars.append((wa * (1 - wa) + wh * (1 - wh)) / n)
        m = sum(dwrs) / len(dwrs)
        var_obs = sum((d - m) ** 2 for d in dwrs) / max(1, len(dwrs) - 1)
        mean_bin = sum(binvars) / len(binvars)
        var_sig = max(0.0, var_obs - mean_bin)
        print(f"  mean dwr {m:+.4f} | SD(point dwr) {math.sqrt(var_obs):.4f} "
              f"| indep binomial floor {math.sqrt(mean_bin):.4f}")
        print(f"  var_signal {var_sig:.5f} -> RMS true dwr "
              f"{math.sqrt(var_sig):.4f}")
        sign_hold = sum(1 for d in dwrs if d < 0)
        print(f"  direction: hold better at {sign_hold}/{len(dwrs)} points "
              f"(dwr<0)")


if __name__ == "__main__":
    main()
