"""search_smoke_read — read the M12 Build 0 search smoke (ev:"search" labels rows).

Usage:
    uv run python scripts/search_smoke_read.py [labels.jsonl] [--games games.jsonl] [--census census.jsonl]

Per searched window the row carries every candidate (0 = pass, then the mask
options) with per-roll leaf values, leaf kinds (leaf / end / draw / void /
timeout / unserved / crash / copy_crash), forward calls and ms, plus the
mainline's natural pick ("nat"). Reports: leaf-kind mix, forward calls and
decisions per leaf, ms per window and per option, copy share, the margin
distribution (max V − V(natural)), how often the search's argmax differs from
the natural pick, and the per-game multiplier: search forward calls vs the
mainline's own bridged asks (from the census).
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

DEF = Path("data/runs/build0-search-smoke")


def q(v, p):
    if not v:
        return None
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("labels", nargs="?", default=str(DEF / "search.jsonl"))
    ap.add_argument("--games", default=str(DEF / "games.jsonl"))
    ap.add_argument("--census", default=str(DEF / "census.jsonl"))
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.labels) if l.startswith('{"ev":"search"')]
    if not rows:
        print("no search rows"); return 1
    kinds: Counter = Counter()
    calls_leaf, ms_window, ms_opt, copy_share, margins, n_opts = [], [], [], [], [], []
    argmax_differs = agree = 0
    per_game_calls: dict = defaultdict(int)
    per_game_windows: dict = defaultdict(int)
    nat_missing = 0
    for r in rows:
        n_opts.append(r["n_opts"])
        ms_window.append(r["ms"])
        per_game_windows[r["i"]] += 1
        if r["ms"]:
            copy_share.append(r["copy_ms"] / r["ms"])
        vals = {}
        for o in r["opts"]:
            for k, c in zip(o["kind"], o["calls"]):
                kinds[k] += 1
                per_game_calls[r["i"]] += c
                if k == "leaf":
                    calls_leaf.append(c)
            ms_opt.append(o["ms"] / max(1, len(o["v"])))
            vs = [v for v in o["v"] if v is not None]
            if vs:
                vals[o["label"]] = st.mean(vs)
        nat = r.get("nat")
        if nat not in vals or not vals:
            nat_missing += 1
            continue
        best = max(vals, key=vals.get)
        margins.append(vals[best] - vals[nat])
        if best == nat:
            agree += 1
        else:
            argmax_differs += 1
    print(f"windows {len(rows)}  games {len(per_game_windows)}  n_opts p50/max {q(n_opts,.5)}/{max(n_opts)}")
    tot = sum(kinds.values())
    print("leaf kinds " + ", ".join(f"{k} {v} ({v/tot:.1%})" for k, v in kinds.most_common()))
    print(f"forward calls per LEAF option p50/p90/max {q(calls_leaf,.5)}/{q(calls_leaf,.9)}/{max(calls_leaf) if calls_leaf else None}"
          f"  (calls − 1 = intermediate decisions before the value ask)")
    print(f"ms per window p50/p90/max {q(ms_window,.5)}/{q(ms_window,.9)}/{max(ms_window)}"
          f"  ms per option-roll p50 {q(ms_opt,.5)}  copy share p50 {q(copy_share,.5):.2f}")
    if margins:
        print(f"margin (max V − V(nat)) p50/p90/p99/max {q(margins,.5):.4f}/{q(margins,.9):.4f}/{q(margins,.99):.4f}/{max(margins):.4f}"
              f"  argmax≠natural {argmax_differs}/{argmax_differs+agree} ({argmax_differs/max(1,argmax_differs+agree):.1%})"
              f"  nat unresolved {nat_missing}")
        for bar in (0.01, 0.02, 0.05, 0.1):
            print(f"   margin ≥ {bar}: {sum(1 for m in margins if m >= bar)/len(margins):.1%}")
    # per-game multiplier
    mainline_asks: Counter = Counter()
    cp = Path(a.census)
    if cp.exists():
        for l in open(cp):
            try:
                r = json.loads(l)
            except json.JSONDecodeError:
                continue
            if r.get("by") == "bridge":
                mainline_asks[r.get("i", r.get("g", -1))] += 1
    games = {}
    gp = Path(a.games)
    if gp.exists():
        for l in open(gp):
            try:
                g = json.loads(l); games[g["i"]] = g
            except (json.JSONDecodeError, KeyError):
                continue
    if games:
        ms = [g["ms"] for g in games.values()]
        print(f"games {len(games)} status {Counter(g['status'] for g in games.values())} ms p50/max {q(ms,.5)}/{max(ms)}"
              f" windows/game p50 {q([g.get('windows',0) for g in games.values()],.5)}")
    sc = [per_game_calls[i] for i in per_game_calls]
    print(f"search forward calls per game p50/max {q(sc,.5)}/{max(sc)}  searched windows/game p50 {q(list(per_game_windows.values()),.5)}")
    if mainline_asks:
        tot_main = sum(mainline_asks.values())
        print(f"mainline bridged asks total {tot_main} (all census rows by=bridge)  search calls total {sum(sc)}"
              f"  → multiplier ≈ {(tot_main + sum(sc))/max(1,tot_main):.2f}× forward calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
