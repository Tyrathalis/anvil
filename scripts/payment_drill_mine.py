#!/usr/bin/env python3
"""M9 rung 3: first-pass payment-drill candidate miner (m9-plan D3 item 3).

Mines a -paytelemetry census (goal-era, §12) for windows where the payment
choice PLAUSIBLY flips a short-horizon outcome, per the m9-plan mining rule
("search logged games for cells where a source tapped for payment was
consequential within 1–2 turns"). This is the RANKING pass only — census
records carry no per-option labels, so candidacy is join-based and the drill
session certifies each candidate by exact replay + engine adjudication
(Grindstone machinery) before anything enters the evalset.

Shape tags (the m9-plan named shapes):
- forced_chain     : forced window (auto-unpayable, plan exists) — automatic
                     candidate, the purest shape.
- blocker_pressure : consequential window by player P, and P declares
                     blockers within the next 2 turns (dork-as-blocker
                     candidacy: what P tapped may have been needed to block).
- color_hold       : consequential window by P with ANOTHER scoped payment
                     window for P later the same turn (the first payment's
                     color/source commitment constrained the second).
- wide_choice      : ≥4 outcome-distinct options (rich decision, generic
                     fallback shape for coverage).
- phyrexian        : the window's SA is on a known phyrexian-mana card
                     (--phy-sa list; census rows carry no per-option
                     labels, so the join is by card name) and ≥2 options
                     exist (the min_life choice surfaced). The mana-vs-
                     life family (§12a min_life goal).

Score = weighted tag sum; output JSONL is provenance-traced (census file,
game index, seed, turn, phase, sa) per the standing provenance rule.

Usage: payment_drill_mine.py <census.jsonl...> [--out candidates.jsonl] [--top N]
"""

import argparse
import json
from collections import defaultdict

WEIGHTS = {"forced_chain": 100, "phyrexian": 50, "blocker_pressure": 10,
           "color_hold": 6, "wide_choice": 3}


def mine_file(path, phy_sa=()):
    """Two passes per file: index combat/payment events per (game, player),
    then tag windows via the short-horizon joins."""
    games = defaultdict(lambda: {"seed": None, "windows": [], "blocks": [], "pays": []})
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            g = r.get("g")
            if r.get("ev") == "start":
                games[g]["seed"] = r.get("seed")
                continue
            m = r.get("m")
            if m == "declareBlockers":
                games[g]["blocks"].append((r.get("t", 0), r.get("p")))
            elif m == "payManaCost" and not r.get("effect") and "goals" in r:
                rec = {
                    "t": r.get("t", 0), "ph": r.get("ph"), "p": r.get("p"),
                    "sa": r.get("sa"), "goals": r.get("goals", 0),
                    "plans": r.get("plans", 0), "conseq": bool(r.get("conseq")),
                    "forced": bool(r.get("forced")), "atoms": r.get("atoms", 0),
                    "srcclasses": r.get("srcclasses", 0),
                }
                games[g]["pays"].append(rec)
                if rec["conseq"]:
                    games[g]["windows"].append(rec)

    out = []
    for g, data in games.items():
        blocks_by_p = defaultdict(list)
        for t, p in data["blocks"]:
            blocks_by_p[p].append(t)
        pays_by_pt = defaultdict(int)
        for rec in data["pays"]:
            pays_by_pt[(rec["p"], rec["t"])] += 1

        for rec in data["windows"]:
            tags = []
            if rec["forced"]:
                tags.append("forced_chain")
            if rec["goals"] >= 2 and any(rec["sa"].startswith(n) for n in phy_sa):
                tags.append("phyrexian")
            if any(rec["t"] <= bt <= rec["t"] + 2 for bt in blocks_by_p.get(rec["p"], [])):
                tags.append("blocker_pressure")
            if pays_by_pt[(rec["p"], rec["t"])] >= 2:
                tags.append("color_hold")
            if rec["goals"] >= 4:
                tags.append("wide_choice")
            if not tags:
                continue
            out.append({
                "source": path, "g": g, "seed": data["seed"],
                **rec, "tags": tags,
                "score": sum(WEIGHTS[t] for t in tags),
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("census", nargs="+")
    ap.add_argument("--out", default=None)
    ap.add_argument("--top", type=int, default=0)
    ap.add_argument("--phy-sa", default=None,
                    help="file of phyrexian-mana card names (one per line) "
                         "for the phyrexian shape tag")
    args = ap.parse_args()

    phy_sa = ()
    if args.phy_sa:
        phy_sa = tuple(x.strip() for x in open(args.phy_sa)
                       if x.strip() and not x.startswith("#"))

    cands = []
    for p in args.census:
        cands.extend(mine_file(p, phy_sa=phy_sa))
    cands.sort(key=lambda c: (-c["score"], c["source"], c["g"], c["t"]))
    if args.top:
        cands = cands[: args.top]

    tag_counts = defaultdict(int)
    for c in cands:
        for t in c["tags"]:
            tag_counts[t] += 1
    print(f"candidates: {len(cands)}")
    for t, n in sorted(tag_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {t:<18} {n}")
    if args.out:
        with open(args.out, "w") as f:
            for c in cands:
                f.write(json.dumps(c) + "\n")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
