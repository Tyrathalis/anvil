#!/usr/bin/env python3
"""M10 ceiling sweep — the named EXPLORATORY reads (m10-ceiling-spec
"Secondary / exploratory reads": inform routing, NEVER gate). Run after
ADR-0078 closed the verdict; consumed by the build design session.

  shapes    what do certified best schedules look like (fork-9 dividend):
            selected-arm length, canonical-shape match (replaying the
            planner's generators per turn), hold share, ramp-first share.
  strata    certification rate by n-bucket / resource-bound (demand >
            capacity, census conventions) / mana-producer presence.
  diverge   where the degrades live: degrade_why / degraded_at by arm
            length, on selected arms and overall; payment-leg health
            (dir/salvage/fail/auto counters across all joint rows).
  slack     best-of-natural-K vs mean at game end (fork-1 free read;
            determinization noise dominates — labeled as such).

Usage:
  uv run python scripts/schedule_explore.py \
      --plan data/runs/sched-sweep-m10 \
      --stores data/trajectories/m10-ceiling-census-20260825-212414
"""

from __future__ import annotations

import argparse
import glob
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schedule_sweep import eligible_turns  # noqa: E402
from veto_knowability import build_card_table  # noqa: E402


def canonical_shapes(row: dict) -> dict[tuple, list[str]]:
    """Replay the planner's canonical generators for one turn ->
    {sequence: [shape names it realizes]} (a sequence can realize several)."""
    cands = row["cands"]
    by_cost_desc = sorted(cands, key=lambda c: (-c["cmc"], c["label"]))
    by_cost_asc = sorted(cands, key=lambda c: (c["cmc"], c["label"]))
    lab = lambda cs: tuple(c["label"] for c in cs)  # noqa: E731
    ramp = sorted([c for c in cands if c["mana_producer"]],
                  key=lambda c: (c["cmc"], c["label"]))
    rest = [c for c in by_cost_desc if not c["mana_producer"]]
    noint = [c for c in by_cost_desc if not c["instant_speed"]]
    shapes: dict[tuple, list[str]] = defaultdict(list)
    shapes[()].append("hold_all")
    shapes[lab(by_cost_desc[:3])].append("greedy_max_spend")
    shapes[lab((ramp + rest)[:3])].append("ramp_first")
    shapes[lab(by_cost_asc[:3])].append("curve_ascending")
    shapes[lab(by_cost_desc)].append("curve_descending")
    shapes[lab(noint[:3])].append("hold_interaction")
    return shapes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default="data/runs/sched-sweep-m10")
    ap.add_argument("--stores", nargs="+", required=True)
    args = ap.parse_args()
    plan = Path(args.plan)

    # inputs
    perturn = {(r["g"], r["t"]): r for r in map(
        json.loads, open(plan / "stage1-perturn.jsonl"))}
    sched: dict = defaultdict(dict)
    for ln in (plan / "sched-h2.tsv").read_text().splitlines():
        if not ln or ln.startswith("#"):
            continue
        f = ln.split("\t")
        sched[(int(f[0]), int(f[1]))][int(f[4])] = (f[5], tuple(f[6:]))
    print("[explore] re-walking the census store for candidate metadata ...")
    rows, _ = eligible_turns(args.stores, build_card_table())
    meta = {(r["g"], r["t"]): r for r in rows}

    out: dict = {}

    # ---------------------------------------------------------- shapes
    shape_cert = Counter()
    shape_read = Counter()
    len_cert = Counter()
    full_set = part_set = 0
    for key, rec in perturn.items():
        if not rec.get("read"):
            continue
        mode_labels = sched[key].get(rec["arm"])
        m = meta.get(key)
        if mode_labels is None or m is None:
            continue
        seq = mode_labels[1]
        names = canonical_shapes(m).get(seq, ["other_ordered_subset"])
        for nm in names:
            shape_read[nm] += 1
            if rec["certified"]:
                shape_cert[nm] += 1
        if rec["certified"]:
            len_cert[len(seq)] += 1
            n = len(m["cands"])
            if len(seq) >= min(n, 3):
                full_set += 1
            else:
                part_set += 1
    out["shapes"] = {
        "selected_certified_by_shape": dict(shape_cert.most_common()),
        "selected_read_by_shape": dict(shape_read.most_common()),
        "certified_arm_length_hist": {str(k): v for k, v in sorted(len_cert.items())},
        "certified_full_vs_partial": [full_set, part_set],
    }

    # ---------------------------------------------------------- strata
    strat = defaultdict(lambda: [0, 0])  # name -> [read, certified]
    for key, rec in perturn.items():
        if not rec.get("read"):
            continue
        m = meta.get(key)
        if m is None:
            continue
        n = len(m["cands"])
        demand = sum(c["cmc"] for c in m["cands"])
        rb = demand > m.get("capacity", 0)
        buckets = [f"n={min(n, 6)}{'+' if n >= 6 else ''}",
                   "resource_bound" if rb else "unbound",
                   "has_rock" if any(c["mana_producer"] for c in m["cands"]) else "no_rock"]
        for b in buckets:
            strat[b][0] += 1
            strat[b][1] += rec["certified"]
    out["strata"] = {b: {"read": v[0], "certified": v[1],
                         "rate": round(v[1] / v[0], 3) if v[0] else None}
                     for b, v in sorted(strat.items())}

    # --------------------------------------------------------- diverge
    why = Counter()
    at_frac = []
    pay = Counter()
    sel_keys = {(r["g"], r["t"], r["arm"]) for r in perturn.values()
                if r.get("read")}
    for f in glob.glob(str(plan / "lanes-h2/lane-*.out.jsonl")):
        for line in open(f):
            r = json.loads(line)
            if r.get("ev") != "sched" or "skip" in r or r.get("arm", 0) == 0:
                continue
            p = r.get("pay")
            if p and r.get("joint"):
                for k in ("dir", "salvage", "fail", "auto", "costmod", "err"):
                    pay[k] += p.get(k, 0)
            if r.get("degrade_why"):
                sel = (r["i"], r["t"], r["arm"]) in sel_keys
                why[("sel:" if sel else "all:") + r["degrade_why"]] += 1
                if r.get("sched_n") and sel:
                    at_frac.append(r.get("degraded_at", 0) / r["sched_n"])
    out["divergence"] = {
        "degrade_why": dict(why.most_common()),
        "selected_degraded_at_frac_mean": round(statistics.mean(at_frac), 3)
        if at_frac else None,
        "joint_pay_counters": dict(pay),
        "pay_salvage_rate": round(pay["salvage"] / max(pay["dir"] + pay["salvage"]
                                                       + pay["fail"], 1), 4),
    }

    # ----------------------------------------------------------- slack
    nat_mean, nat_best, arm_win = [], [], []
    positives = {(r["g"], r["t"]): r for r in map(
        json.loads, open(plan / "positives.jsonl"))}
    per = defaultdict(lambda: defaultdict(dict))
    for f in glob.glob(str(plan / "lanes-end/lane-*.out.jsonl")):
        for line in open(f):
            r = json.loads(line)
            if r.get("ev") != "sched" or "skip" in r:
                continue
            per[(r["i"], r["t"])][r["arm"]][r["roll"]] = r
    for key, arms in per.items():
        pos = positives.get(key)
        if pos is None:
            continue
        seat = pos["seat"]
        def w(r):
            v = r.get("winner", -1)
            return 1.0 if v == seat else (0.0 if v == (1 - seat) else 0.5)
        nats = [w(r) for r in arms.get(0, {}).values() if r.get("ended")]
        sel = [w(r) for r in arms.get(pos["arm"], {}).values() if r.get("ended")]
        if len(nats) >= 4:
            nat_mean.append(statistics.mean(nats))
            nat_best.append(max(nats))
        if sel:
            arm_win.append(statistics.mean(sel))
    out["natural_slack"] = {
        "turns": len(nat_mean),
        "nat_mean_win": round(statistics.mean(nat_mean), 4) if nat_mean else None,
        "nat_best_of_k_win": round(statistics.mean(nat_best), 4) if nat_best else None,
        "selected_arm_win": round(statistics.mean(arm_win), 4) if arm_win else None,
        "note": "best-of-K over determinized rolls confounds policy slack "
                "with library-order luck — context only",
    }

    json.dump(out, open(plan / "exploratory-reads.json", "w"), indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
