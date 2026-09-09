#!/usr/bin/env python3
"""M12 Build 3 (ADR-0105): the served-surface census of a run — per surface
callback answered over the bridge (Census rows with by=bridge on the surface
methods), the count, the accepted share (ok), the gate mix (mode) and the
answer-length mix (k), plus the model server's fallbacks per surface tag from
its dump when present. Usage:
  uv run python scripts/surface_served_census.py <run dir with census.jsonl or workers/inv-*/census.jsonl> [server.log]
"""
from __future__ import annotations

import glob
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SURF = {"chooseSingleEntityForEffect", "chooseSingleCardForZoneChange", "chooseSingleSpellForEffect",
        "chooseEntitiesForEffect", "chooseCardsForEffect", "chooseCardsToDiscardFrom",
        "chooseCardsToDiscardToMaximumHandSize", "choosePermanentsToSacrifice", "choosePermanentsToDestroy",
        "chooseSpellAbilitiesForEffect", "chooseModeForAbility", "orderSimultaneousSa", "orderMoveToZoneList",
        "orderBlockers", "orderAttackers", "assignCombatDamage"}


def main() -> None:
    run = Path(sys.argv[1])
    files = [run / "census.jsonl"] if (run / "census.jsonl").exists() else [Path(p) for p in glob.glob(str(run / "workers/inv-*/census.jsonl"))]
    by: dict[str, Counter] = defaultdict(Counter)
    pay: dict[str, Counter] = defaultdict(Counter)  # evening 4: payManaCost by=bridge (mainline) / copy rows
    games = 0
    for f in files:
        for ln in open(f):
            if '"payManaCost"' in ln and ('"by":' in ln) and ('"conseq":true' in ln or '"reff":true' in ln):
                try:
                    r = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if r.get("reff"):
                    c = pay["resolution-effect (-paytelemetry)"]
                    c["windows"] += 1
                    if r.get("zero"):
                        c["zero_cost"] += 1
                    elif r.get("enumerr"):
                        c["enumerr"] += 1
                    else:
                        c["mana"] += 1
                        c["conseq"] += 1 if r.get("conseq") else 0
                        c["costmod"] += 1 if r.get("costmod") else 0
                        c["not_autoable"] += 0 if r.get("autoable") else 1
                    continue
                c = pay["copy (search)" if r.get("copy") else "mainline"]
                c["windows"] += 1
                c[f"by:{r.get('by')}"] += 1
                c["goal" if r.get("pick") != "auto" else "auto"] += 1
                if r.get("exec"):
                    c[f"exec:{r['exec']}"] += 1
                if r.get("forced"):
                    c["forced"] += 1
                continue
            if '"by":"bridge"' not in ln:
                if ln.startswith('{"ev":"start"'):
                    games += 1
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            m = r.get("m")
            if m not in SURF:
                continue
            c = by[m]
            c["asked"] += 1
            c["ok"] += 1 if r.get("ok") else 0
            if "gate" in r:
                c[f"gate:{r['gate']}"] += 1
            if "k" in r:
                c[f"k:{r['k']}"] += 1
            if "n" in r:
                c["n_sum"] += int(r["n"])
    print(f"games {games}")
    print("| callback | asked | ok | ok share | mean n | k / gate mix |")
    print("|---|---|---|---|---|---|")
    for m, c in sorted(by.items(), key=lambda x: -x[1]["asked"]):
        mix = ", ".join(f"{k} {v}" for k, v in sorted(c.items()) if k.startswith(("k:", "gate:")))
        print(f"| {m} | {c['asked']} | {c['ok']} | {c['ok'] / max(1, c['asked']):.3f} | {c['n_sum'] / max(1, c['asked']):.1f} | {mix} |")
    if pay:
        print("payment windows (evening 4):")
        for k, c in sorted(pay.items()):
            print(f"  {k}: " + ", ".join(f"{kk} {vv}" for kk, vv in sorted(c.items())))
    if len(sys.argv) > 2:
        log = Path(sys.argv[2]).read_text(errors="replace")
        pb = Counter(re.findall(r"pay_bar_(auto|goal)", log))
        if pb:
            print("server pay bar:", dict(pb))
        fb = Counter(re.findall(r"MODEL ERROR on (mtg\.surface\.\w+)", log))
        errs = Counter(re.findall(r"MODEL ERROR on (mtg\.surface\.\w+) seq=\d+: (\w+)", log))
        print("server MODEL ERROR per surface tag:", dict(fb) or "none")
        if errs:
            print("  by class:", dict(errs))


if __name__ == "__main__":
    main()
