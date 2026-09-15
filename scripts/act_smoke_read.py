#!/usr/bin/env python3
"""act_smoke_read — the evening 5 acting smoke's read (ADR-0106 A).

Reads one build3_act_smoke.sh output dir: the ev:"search" rows (search.jsonl)
for the option stage (by) and the answer stage (ans.by, per kind), the
mainline arms' outcomes from the census (surfaceAct rows: act / miss:<why> /
unfired, by kind and by when — played | stale), the copy kinds, and the
copy forward calls per game and per searched window (games.jsonl). Usage: act_smoke_read.py <dir>
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def main() -> None:
    d = Path(sys.argv[1])
    by = Counter()
    ans_by = Counter()
    ans_kind = Counter()
    applied = Counter()
    copy_kinds = Counter()
    lifted = 0
    windows = 0
    sub_rows = 0
    copy_calls = 0
    margins = []
    ans_margins = []
    for ln in open(d / "search.jsonl"):
        if not ln.startswith('{"ev":"search"'):
            continue
        r = json.loads(ln)
        windows += 1
        by[r.get("by", "telemetry")] += 1
        applied[r.get("applied", "-")] += 1
        if r.get("margin") is not None:
            margins.append(r["margin"])
        if r.get("lifted"):
            lifted += 1
        for o in r.get("opts") or []:
            for k in o.get("kind") or []:
                copy_kinds[k] += 1
            copy_calls += sum(o.get("calls") or [])
        for s in r.get("sub") or []:
            sub_rows += 1
            for a in s.get("ans") or []:
                for k in a.get("kind") or []:
                    copy_kinds[f"sub:{k}"] += 1
                copy_calls += sum(a.get("calls") or [])
        a = r.get("ans")
        if a:
            ans_by[a["by"]] += 1
            if a.get("kind"):
                ans_kind[(a["kind"], a["by"])] += 1
            if a.get("margin") is not None:
                ans_margins.append(a["margin"])
    arms = Counter()
    arm_kind = Counter()
    crashes = Counter()
    cpath = d / "census.jsonl"
    if cpath.exists():
        for ln in open(cpath):
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("m") == "surfaceAct" or r.get("method") == "surfaceAct":
                arms[(r.get("outcome"), r.get("at"))] += 1
                arm_kind[(r.get("kind"), r.get("outcome"))] += 1
    games = 0
    gpath = d / "games.jsonl"
    if gpath.exists():
        for ln in open(gpath):
            try:
                g = json.loads(ln)
            except json.JSONDecodeError:
                continue
            games += 1
            if g.get("crash") or g.get("error"):
                crashes[str(g.get("crash") or g.get("error"))[:80]] += 1
    print(f"games {games}  searched windows {windows}  sub rows {sub_rows}  windows with a lift {lifted}")
    print(f"option stage by: {dict(by)}  applied: {dict(applied)}")
    if margins:
        print(f"  option margin mean {sum(margins)/len(margins):.4f}  n {len(margins)}")
    print(f"answer stage by: {dict(ans_by)}")
    print(f"  per (kind, by): {dict(ans_kind)}")
    if ans_margins:
        print(f"  answer margin mean {sum(ans_margins)/len(ans_margins):.4f}  n {len(ans_margins)}")
    print(f"mainline arms (outcome, at): {dict(arms)}")
    print(f"  per (kind, outcome): {dict(arm_kind)}")
    print(f"copy kinds: {dict(copy_kinds)}")
    if games:
        print(f"copy forward calls {copy_calls}: {copy_calls / games:.0f} per game, "
              f"{copy_calls / max(1, windows):.1f} per searched window (windows/game {windows / games:.0f})")
    if crashes:
        print(f"crashes: {dict(crashes)}")


if __name__ == "__main__":
    main()
