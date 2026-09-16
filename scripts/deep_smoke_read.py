#!/usr/bin/env python3
"""deep_smoke_read — the partial-expansion slot's smoke read (ADR-0106 C3).

Reads one build3_act_smoke.sh output dir run with DEEP=<B>: per searched
window the deep gate's verdict (deep.by: gate | band | floor | single |
nat_unvalued), the option verdict (by) split by whether the deep round ran,
the shallow-vs-deep flip rate (the deep round's argmax vs the first ply's),
the deep set size, the deep copies' leaf kinds / forward calls / wall, and
the cost: deep copy calls per game beside the first-ply + surface copies,
wall per deep window. Usage: deep_smoke_read.py <dir>
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path


def q(a, p):
    if not a:
        return None
    a = sorted(a)
    return a[int(p * (len(a) - 1))]


def main() -> None:
    d = Path(sys.argv[1])
    deep_by = Counter()
    by_ran = Counter()
    by_not = Counter()
    set_sizes = []
    flips = 0
    ran = 0
    deep_kinds = Counter()
    deep_calls = 0
    other_calls = 0
    deep_ms = []
    win_ms = []
    windows = 0
    games = set()
    for ln in open(d / "search.jsonl"):
        if not ln.startswith('{"ev":"search"'):
            continue
        r = json.loads(ln)
        windows += 1
        games.add(r["i"])
        win_ms.append(r.get("ms", 0))
        for o in r.get("opts") or []:
            other_calls += sum(o.get("calls") or [])
        for s in r.get("sub") or []:
            for a in s.get("ans") or []:
                other_calls += sum(a.get("calls") or [])
        dp = r.get("deep")
        if not dp:
            deep_by["off"] += 1
            by_not[r.get("by", "telemetry")] += 1
            continue
        deep_by[dp["by"]] += 1
        if dp["by"] in ("band", "floor", "nat_unvalued"):
            ran += 1
            by_ran[r.get("by")] += 1
            set_sizes.append(len(dp.get("set") or []))
            vs = dp.get("v") or []
            if vs and any(v is not None for v in vs):
                arg = dp["set"][max(range(len(vs)), key=lambda i: -1 if vs[i] is None else vs[i])]
                if arg != dp.get("shallow_arg"):
                    flips += 1
            ms = 0
            for c in dp.get("copies") or []:
                for k in c.get("kind") or []:
                    deep_kinds[k] += 1
                deep_calls += sum(c.get("calls") or [])
                ms += c.get("ms", 0)
            deep_ms.append(ms)
        else:
            by_not[r.get("by")] += 1
    ng = max(1, len(games))
    print(f"windows {windows}  games {len(games)}  deep gate: " + ", ".join(f"{k} {v}" for k, v in deep_by.most_common()))
    print(f"deep ran {ran} ({ran / max(1, windows):.1%} of windows); set size mean {st.mean(set_sizes) if set_sizes else None}; "
          f"deep argmax flips the first ply's {flips}/{ran}")
    print("option verdict where deep ran: " + ", ".join(f"{k} {v}" for k, v in by_ran.most_common()))
    print("option verdict elsewhere:      " + ", ".join(f"{k} {v}" for k, v in by_not.most_common()))
    print("deep copy kinds: " + ", ".join(f"{k} {v}" for k, v in deep_kinds.most_common()))
    print(f"forward calls per game: deep copies {deep_calls / ng:.0f}, first-ply + surface copies {other_calls / ng:.0f} "
          f"(deep share {deep_calls / max(1, deep_calls + other_calls):.1%})")
    print(f"wall per deep round p50/p90/max {q(deep_ms, .5)}/{q(deep_ms, .9)}/{max(deep_ms) if deep_ms else None} ms; "
          f"searched window p50/p90 {q(win_ms, .5)}/{q(win_ms, .9)} ms (first ply + surfaces; the deep round is outside it)")
    games_rows = [json.loads(l) for l in open(d / "games.jsonl")] if (d / "games.jsonl").exists() else []
    if games_rows:
        st_ = Counter(g.get("status") for g in games_rows)
        walls = [g.get("ms", 0) / 1000 for g in games_rows]
        print(f"games {len(games_rows)}: status {dict(st_)}; wall/game p50 {q(walls, .5):.0f} s max {max(walls):.0f} s")


if __name__ == "__main__":
    main()
