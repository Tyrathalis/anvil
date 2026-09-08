#!/usr/bin/env python3
"""M12 Build 3 (ADR-0105): the exposure split of a paired surface read — the
on − off paired diff over games grouped by whether the ON arm served an
answer on the named surface callbacks (Census by=bridge, ok), per callback
and pooled ("any"). Pairs are the same game index across the two arms' seat
runs (build2_read.paired's join); a census game joins its arm's games by
seed (the census "start" row). Attribute-before-rerunning (standing rule).

CAVEAT (evening 3, 09-08): exposure keyed on ONE arm's game is post-treatment
— a window that fires when the seat's board survived selects that arm's
better games, and the split's sign follows the conditioning arm (trigger
ordering: +9.6 keyed on ON, -2.2 keyed on OFF, the same 580 pairs). Use
--key fired --arm both (the window fired in both arms' games) for a
symmetric key, and treat any split as exploratory; ablation arms on one
reference are the attribution instrument.

Usage: uv run python scripts/surface_exposure_read.py --on <s0dir>,<s1dir> --off <s0dir>,<s1dir> \\
           [--callbacks orderSimultaneousSa,orderMoveToZoneList,assignCombatDamage] [--out x.json]
"""
from __future__ import annotations

import argparse
import glob
import json
import math
from collections import defaultdict
from pathlib import Path


def served_by_seed(run_dir: Path, callbacks: set[str]) -> dict[int, dict[str, int]]:
    """seed -> {callback: served-and-accepted answers} over the run's workers."""
    out: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for f in glob.glob(str(run_dir / "workers/inv-*/census.jsonl")):
        g_seed: dict[int, int] = {}
        for ln in open(f):
            if ln.startswith('{"ev":"start"'):
                r = json.loads(ln)
                g_seed[r["g"]] = r["seed"]
                continue
            if '"by":"bridge"' not in ln:
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("m") in callbacks and r.get("ok", True) and r.get("g") in g_seed:
                out[g_seed[r["g"]]][r["m"]] += 1
    return out


SIZE_FIELD = {"orderSimultaneousSa": "activePlayerSAs", "orderMoveToZoneList": "cards",
              "assignCombatDamage": "blockers", "chooseModeForAbility": "possible"}


def fired_by_seed(run_dir: Path, callbacks: set[str]) -> dict[int, dict[str, int]]:
    """seed -> {callback: nontrivial windows (>= 2 options) for the model seat},
    served or not — the exposure key that does not depend on the arm's own
    answers (--key fired --arm off: the counterfactual game's windows)."""
    out: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for f in glob.glob(str(run_dir / "workers/inv-*/census.jsonl")):
        g_seed: dict[int, int] = {}
        for ln in open(f):
            if ln.startswith('{"ev":"start"'):
                r = json.loads(ln)
                g_seed[r["g"]] = r["seed"]
                continue
            if '"by":"bridge"' in ln:
                continue  # the served-answer row of the same window
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            m = r.get("m")
            if m in callbacks and str(r.get("p", "")).startswith("Anvil") and r.get("g") in g_seed:
                if int(r.get(SIZE_FIELD.get(m, ""), 0) or 0) >= 2:
                    out[g_seed[r["g"]]][m] += 1
    return out


def stat(diffs: list[int]) -> dict:
    n = len(diffs)
    if n < 2:
        return {"n": n}
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    se = math.sqrt(var / n)
    return {"n": n, "diff_pp": round(mean * 100, 2), "se_pp": round(se * 100, 2), "t": round(mean / se, 2) if se else None}


def main() -> None:
    from build2_read import _games, _model_prefix, _wins

    ap = argparse.ArgumentParser()
    ap.add_argument("--on", required=True)
    ap.add_argument("--off", required=True)
    ap.add_argument("--callbacks", default="orderSimultaneousSa,orderMoveToZoneList,assignCombatDamage")
    ap.add_argument("--out")
    ap.add_argument("--key", default="served", choices=["served", "fired"],
                    help="served = the ON arm answered it; fired = the window existed (>= 2 options) in --arm")
    ap.add_argument("--arm", default="on", choices=["on", "off", "both"],
                    help="which arm's game defines exposure (both = the window fired in BOTH arms' games)")
    a = ap.parse_args()
    cbs = set(a.callbacks.split(","))
    on_dirs = [Path(p) for p in a.on.split(",")]
    off_dirs = [Path(p) for p in a.off.split(",")]
    groups: dict[str, list[int]] = defaultdict(list)
    for od, fd in zip(on_dirs, off_dirs):
        og, fg = _games(od), _games(fd)
        ow, fw = _wins(og, _model_prefix(od)), _wins(fg, _model_prefix(fd))
        key_fn = served_by_seed if a.key == "served" else fired_by_seed
        if a.arm == "both":
            s_on, s_off = key_fn(od, cbs), key_fn(fd, cbs)
            served = {sd: {cb: 1 for cb in cbs if s_on.get(sd, {}).get(cb) and s_off.get(sd, {}).get(cb)}
                      for sd in set(s_on) | set(s_off)}
            served = {sd: v for sd, v in served.items() if v}
        else:
            served = key_fn(od if a.arm == "on" else fd, cbs)
        for i in sorted(set(ow) & set(fw)):
            if og[i].get("seed") != fg[i].get("seed"):
                raise SystemExit(f"game {i}: seeds differ between arms — not paired")
            d = ow[i] - fw[i]
            s = served.get(og[i]["seed"], {})
            groups["all"].append(d)
            groups["any:exposed" if s else "any:unexposed"].append(d)
            for cb in sorted(cbs):
                groups[f"{cb}:{'exposed' if s.get(cb) else 'unexposed'}"].append(d)
    res = {k: stat(v) for k, v in groups.items()}
    print("| group | n | on − off pp | ± se | t |")
    print("|---|---|---|---|---|")
    for k in sorted(res, key=lambda k: (k != "all", k)):
        r = res[k]
        if r.get("n", 0) < 2:
            print(f"| {k} | {r.get('n', 0)} | | | |")
        else:
            print(f"| {k} | {r['n']} | {r['diff_pp']:+.2f} | {r['se_pp']:.2f} | {r['t']} |")
    if a.out:
        json.dump({"callbacks": sorted(cbs), "on": a.on, "off": a.off, "key": a.key, "arm": a.arm, "groups": res},
                  open(a.out, "w"), indent=1)


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
