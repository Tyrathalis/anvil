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
    games = 0
    for f in files:
        for ln in open(f):
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
    if len(sys.argv) > 2:
        log = Path(sys.argv[2]).read_text(errors="replace")
        fb = Counter(re.findall(r"MODEL ERROR on (mtg\.surface\.\w+)", log))
        errs = Counter(re.findall(r"MODEL ERROR on (mtg\.surface\.\w+) seq=\d+: (\w+)", log))
        print("server MODEL ERROR per surface tag:", dict(fb) or "none")
        if errs:
            print("  by class:", dict(errs))


if __name__ == "__main__":
    main()
