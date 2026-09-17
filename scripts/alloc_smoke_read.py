#!/usr/bin/env python3
"""The allocation head's smoke read (Build 4, ADR-0109 item 2; the alloc tip
`a37bc6a8b4`): from a search run's labels (search.jsonl / workers/*/labels.jsonl)
under -searchalloc — the allocation census (head / floor / unserved / skip per
candidate window), the head's p distribution on searched vs skipped windows,
the acts (by=search) captured on head vs floor windows (the floor's act rate
estimates the act rate the skipped windows would have had: recall ≈
head acts / (head acts + skip share × floor act rate / floor share)), the
forward-call share searched, and the ask's wall. Usage:
  uv run python scripts/alloc_smoke_read.py <labels.jsonl | run dir> [...]
"""
from __future__ import annotations

import collections
import glob
import json
import sys

import numpy as np


def rows_of(paths):
    for p in paths:
        files = [p] if p.endswith(".jsonl") else glob.glob(f"{p}/workers/*/labels.jsonl") + glob.glob(f"{p}/search.jsonl")
        for f in files:
            for line in open(f):
                if '"alloc"' in line:
                    yield json.loads(line)


def main() -> None:
    by = collections.Counter()
    p_by = collections.defaultdict(list)
    acts = collections.Counter()
    calls = collections.Counter()
    ms = []
    games = set()
    for r in rows_of(sys.argv[1:]):
        a = r.get("alloc")
        if not a:
            continue
        games.add((r.get("i"), r.get("seed")))
        b = a["by"]
        by[b] += 1
        if a.get("p") is not None:
            p_by[b].append(a["p"])
        if a.get("ms") is not None:
            ms.append(a["ms"])
        if r.get("ev") == "search":
            c = sum(sum(x for x in o.get("calls", []) if isinstance(x, (int, float))) for o in r.get("opts", []))
            calls[b] += c
            if r.get("by") == "search":
                acts[b] += 1
    n = sum(by.values())
    if not n:
        print("no alloc rows"); return
    print(f"windows {n} in {len(games)} games: " + ", ".join(f"{k} {v} ({v / n:.1%})" for k, v in by.most_common()))
    for k, v in p_by.items():
        v = np.array(v)
        print(f"  p | {k:8s}: mean {v.mean():.3f} p10 {np.percentile(v, 10):.3f} p50 {np.percentile(v, 50):.3f} p90 {np.percentile(v, 90):.3f}")
    searched = n - by["skip"]
    print(f"searched {searched} ({searched / n:.1%} of windows); acts: " + ", ".join(f"{k} {acts[k]}/{by[k]} ({acts[k] / max(1, by[k]):.1%})" for k in ("head", "floor", "unserved") if by[k]))
    if by["floor"] and by["skip"]:
        floor_rate = acts["floor"] / by["floor"]
        est_skipped_acts = by["skip"] * floor_rate
        rec = acts["head"] / max(1e-9, acts["head"] + est_skipped_acts)
        print(f"  estimated recall of acts by the head (floor act rate {floor_rate:.1%} on the {by['skip']} skipped): {rec:.2f}")
    tot_calls = sum(calls.values())
    print(f"copy forward calls: " + ", ".join(f"{k} {calls[k]}" for k in calls) + f" (total {tot_calls}; per game {tot_calls / max(1, len(games)):.0f})")
    if ms:
        m = np.array(ms)
        print(f"alloc ask wall ms: mean {m.mean():.1f} p50 {np.percentile(m, 50):.0f} p90 {np.percentile(m, 90):.0f} max {m.max()}")


if __name__ == "__main__":
    main()
