#!/usr/bin/env python3
"""deep_bench_read — the partial-expansion slot's price (ADR-0106 C3).

Two fleet_bench.py runs on one jar (recipe vs recipe + -searchdeep): per arm,
from the cells' labels (data/runs/<name>-w24s2-*/workers/*/labels.jsonl) the
forward calls per game split first-ply / surface / deep copies, the searched
windows per game, the deep gate census and the deep round's share of copy
wall; from bench.md the g/h (one cell per arm — a draw, not a read; the
ratio is what the equal-box-time split needs). Usage:
    deep_bench_read.py <recipe bench dir> <deep bench dir>
"""
from __future__ import annotations

import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path


def read_arm(bench_dir: Path) -> dict:
    name = bench_dir.name
    dirs = sorted(glob.glob(str(bench_dir.parent / f"{name}-w*s*-*")))
    files = [f for d in dirs for f in glob.glob(f"{d}/workers/*/labels.jsonl")]
    games = set()
    windows = 0
    calls = Counter()
    ms = Counter()
    gate = Counter()
    by = Counter()
    deep_kinds = Counter()
    for f in files:
        with open(f) as fh:
            for ln in fh:
                if not ln.startswith('{"ev":"search"'):
                    continue
                r = json.loads(ln)
                windows += 1
                games.add((f, r["i"]))
                by[r.get("by", "-")] += 1
                for o in r.get("opts") or []:
                    calls["first"] += sum(o.get("calls") or [])
                    ms["first"] += o.get("ms", 0)
                for s in r.get("sub") or []:
                    for a in s.get("ans") or []:
                        calls["surface"] += sum(a.get("calls") or [])
                dp = r.get("deep")
                gate[dp["by"] if dp else "off"] += 1
                for c in (dp or {}).get("copies") or []:
                    calls["deep"] += sum(c.get("calls") or [])
                    ms["deep"] += c.get("ms", 0)
                    for k in c.get("kind") or []:
                        deep_kinds[k] += 1
    ng = max(1, len(games))
    table = (bench_dir / "bench.md").read_text() if (bench_dir / "bench.md").exists() else ""
    row = re.search(r"^\| 24 \| 2 \| (\d+) \| ([\d.]+) \| (\d+) \| (\d+) \|", table, re.M)
    return {
        "name": name, "games": len(games), "windows_per_game": windows / ng,
        "calls_per_game": {k: v / ng for k, v in calls.items()},
        "copy_ms_per_game": {k: v / ng for k, v in ms.items()},
        "gate": dict(gate), "by": dict(by), "deep_kinds": dict(deep_kinds),
        "bench": {"done": int(row.group(1)), "wall_min": float(row.group(2)), "gh_wall": int(row.group(3)),
                  "gh_peak": int(row.group(4))} if row else None,
    }


def main() -> None:
    arms = [read_arm(Path(p)) for p in sys.argv[1:3]]
    for a in arms:
        tot = sum(a["calls_per_game"].values())
        print(f"{a['name']}: games {a['games']}, searched windows/game {a['windows_per_game']:.1f}, "
              f"copy forward calls/game {tot:.0f} = " + " + ".join(f"{k} {v:.0f}" for k, v in a["calls_per_game"].items()))
        print("  copy wall/game (s): " + ", ".join(f"{k} {v / 1000:.0f}" for k, v in a["copy_ms_per_game"].items()))
        print(f"  deep gate {a['gate']}; option verdict {a['by']}; deep copy kinds {a['deep_kinds']}")
        print(f"  bench {a['bench']}")
    if len(arms) == 2 and all(a["bench"] for a in arms):
        r, d = arms
        c = sum(d["calls_per_game"].values()) / max(1, sum(r["calls_per_game"].values()))
        print(f"deep / recipe: forward calls per game x{c:.2f}; g/h peak {r['bench']['gh_peak']} -> {d['bench']['gh_peak']} "
              f"(x{r['bench']['gh_peak'] / max(1, d['bench']['gh_peak']):.2f} box time per game); "
              f"g/h wall {r['bench']['gh_wall']} -> {d['bench']['gh_wall']}")


if __name__ == "__main__":
    main()
