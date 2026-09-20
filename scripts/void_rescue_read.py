#!/usr/bin/env python3
"""The void-rescue instrument's read (ADR-0114; the fork tip's `-searchvoidrescue`).

From a search run's labels (search.jsonl / workers/*/labels.jsonl) recorded with the
rescue on: every first-ply candidate whose roll-0 copy VOIDED (the model's forced ask
vetoed by the realizer, or passed despite the mask) got one more copy on the same
roll seed with the forced option realized by the heuristic's planner, recorded under
the option's "h" block (kind / v / calls / ms / plan / refuse) beside the void's
reason "vr" — never entering the acting rule. The read answers the two priced
questions of ADR-0114:

  1. the void class by reason and by option group, and what fraction of it the
     heuristic realizes (the rescue rate) vs refuses (AiPlayDecision census);
  2. for the rescued leaves, the value against the window's best valued candidate
     and against the natural line on the SAME roll seed (CRN, roll 0): the margin
     distribution, the share clearing the acting bar, and per window whether a
     rescue would have changed the acting decision;

plus the price (rescue forward calls vs the first ply's) and the plan census (how
many rescued plans carry targets / X — where a decoder label would be non-trivial).

Usage:
  uv run python scripts/void_rescue_read.py <labels.jsonl | run dir> [...] [--bar 0.10] [--out read.json]
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import sys

import numpy as np


def rows_of(paths):
    for p in paths:
        files = [p] if p.endswith(".jsonl") else sorted(
            glob.glob(f"{p}/workers/*/labels.jsonl") + glob.glob(f"{p}/search.jsonl"))
        for f in files:
            for line in open(f):
                if '"ev":"search"' in line or '"ev": "search"' in line:
                    r = json.loads(line)
                    if r.get("ev") == "search":
                        yield r


def group_of(label: str) -> str:
    if label.startswith("Play") or "Play land" in label:
        return "land"
    head = label[:25]
    if "{" in head and ":" in head:
        return "ability"
    return "spell"


def pct(a, b) -> str:
    return f"{100.0 * a / b:.1f}%" if b else "n/a"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--bar", type=float, default=0.10, help="the acting bar the margins are read against")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    games = set()
    rows = 0
    rows_with_void = 0
    rows_with_rescue_on = 0
    n_first = collections.Counter()          # first-ply candidate copies by roll-0 kind
    void_by_reason = collections.Counter()
    void_by_group = collections.Counter()
    void_total = 0
    h_kind = collections.Counter()           # the rescue copy's outcome
    h_kind_by_group = collections.Counter()
    refuse = collections.Counter()
    resc_calls = 0
    first_calls = 0
    resc_ms = 0
    first_ms = 0
    plans = collections.Counter()            # rescued plans: targets / x / plain
    margins_best = []                        # h.v - best valued roll-0 value
    margins_nat = []                         # h.v - the natural's roll-0 value (when valued)
    beats_best = 0
    n_valued_rescue = 0
    win_best_margin = []                     # per window: max over rescued of (h.v - best0)
    win_changed = 0
    win_changed_by_applied = collections.Counter()
    applied_census = collections.Counter()
    by_group_margin = collections.defaultdict(list)

    for r in rows_of(a.paths):
        rows += 1
        games.add((r.get("i"), r.get("seed")))
        opts = r.get("opts") or []
        # roll-0 values of every valued candidate (CRN: the same determinization)
        v0 = {}
        for o in opts:
            kinds = o.get("kind") or []
            vs = o.get("v") or []
            if kinds:
                n_first[kinds[0]] += 1
            if vs and vs[0] is not None:
                v0[o["o"]] = float(vs[0])
        best0 = max(v0.values()) if v0 else None
        nat_label = r.get("nat")
        nat_v0 = None
        for o in opts:
            if o.get("label") == nat_label and o["o"] in v0:
                nat_v0 = v0[o["o"]]
                break
        voids = [o for o in opts if (o.get("kind") or [None])[0] == "void" and o.get("o", 0) != 0]
        if voids:
            rows_with_void += 1
        if any("h" in o for o in opts):
            rows_with_rescue_on += 1
        first_calls += sum(int(c) for o in opts for c in (o.get("calls") or []))
        first_ms += sum(int(o.get("ms") or 0) for o in opts)
        applied = r.get("applied") or "none"
        applied_census[applied] += 1
        best_resc_margin = None
        for o in voids:
            void_total += 1
            g = group_of(o.get("label") or "")
            void_by_group[g] += 1
            void_by_reason[o.get("vr") or "unrecorded"] += 1
            h = o.get("h")
            if not h:
                continue
            h_kind[h.get("kind")] += 1
            h_kind_by_group[(g, h.get("kind"))] += 1
            resc_calls += int(h.get("calls") or 0)
            resc_ms += int(h.get("ms") or 0)
            if h.get("refuse"):
                refuse[h["refuse"]] += 1
            plan = h.get("plan")
            if plan is not None:
                if plan.get("tgt"):
                    plans["targets"] += 1
                elif "x" in plan:
                    plans["x"] += 1
                else:
                    plans["plain"] += 1
            if h.get("kind") == "leaf" and h.get("v") is not None:
                hv = float(h["v"])
                n_valued_rescue += 1
                if best0 is not None:
                    m = hv - best0
                    margins_best.append(m)
                    by_group_margin[g].append(m)
                    if m > 0:
                        beats_best += 1
                    best_resc_margin = m if best_resc_margin is None else max(best_resc_margin, m)
                if nat_v0 is not None:
                    margins_nat.append(hv - nat_v0)
        if best_resc_margin is not None:
            win_best_margin.append(best_resc_margin)
            if best_resc_margin >= a.bar:
                win_changed += 1
                win_changed_by_applied[applied] += 1

    def q(xs):
        if not xs:
            return "n/a"
        x = np.asarray(xs)
        return (f"n {len(x)} mean {x.mean():+.4f} p10 {np.percentile(x, 10):+.4f} p50 {np.percentile(x, 50):+.4f} "
                f"p90 {np.percentile(x, 90):+.4f} | ≥0 {pct((x >= 0).sum(), len(x))} ≥0.02 {pct((x >= 0.02).sum(), len(x))} "
                f"≥0.05 {pct((x >= 0.05).sum(), len(x))} ≥{a.bar:g} {pct((x >= a.bar).sum(), len(x))}")

    n_cand = sum(n_first.values())
    out = []
    out.append(f"rows {rows} in {len(games)} games; rows with a void candidate {rows_with_void} "
               f"({pct(rows_with_void, rows)}); rows carrying the instrument {rows_with_rescue_on}")
    out.append(f"first-ply candidates {n_cand}: " + ", ".join(f"{k} {v} ({pct(v, n_cand)})" for k, v in n_first.most_common()))
    out.append(f"void candidates {void_total} by reason: " + ", ".join(f"{k} {v} ({pct(v, void_total)})" for k, v in void_by_reason.most_common()))
    out.append("void by option group: " + ", ".join(f"{k} {v} ({pct(v, void_total)})" for k, v in void_by_group.most_common()))
    n_h = sum(h_kind.values())
    out.append(f"rescue copies {n_h}: " + ", ".join(f"{k} {v} ({pct(v, n_h)})" for k, v in h_kind.most_common()))
    for g in ("spell", "ability", "land"):
        tot = sum(v for (gg, k), v in h_kind_by_group.items() if gg == g)
        leaf = h_kind_by_group.get((g, "leaf"), 0)
        out.append(f"  {g}: rescued to a leaf {leaf}/{tot} ({pct(leaf, tot)})")
    out.append("heuristic refusals: " + ", ".join(f"{k} {v}" for k, v in refuse.most_common(12)))
    out.append("rescued plans: " + ", ".join(f"{k} {v} ({pct(v, sum(plans.values()))})" for k, v in plans.most_common()))
    out.append(f"price: rescue calls {resc_calls} vs first-ply calls {first_calls} (+{pct(resc_calls, first_calls)}); "
               f"rescue wall {resc_ms / 1000:.0f} s vs first-ply {first_ms / 1000:.0f} s (+{pct(resc_ms, first_ms)})")
    out.append(f"rescued leaf value − best valued candidate (roll 0, CRN): {q(margins_best)}")
    out.append(f"rescued leaf value − the natural line (roll 0, CRN): {q(margins_nat)}")
    for g, xs in by_group_margin.items():
        out.append(f"  {g}: {q(xs)}")
    out.append(f"per window (best rescued − best valued): {q(win_best_margin)}")
    out.append(f"windows where a rescue clears the bar {a.bar:g} over the best valued candidate: {win_changed}/{rows} "
               f"({pct(win_changed, rows)}) — by the mainline's applied class: "
               + ", ".join(f"{k} {v}/{applied_census[k]}" for k, v in win_changed_by_applied.most_common()))
    out.append("applied census: " + ", ".join(f"{k} {v}" for k, v in applied_census.most_common()))
    text = "\n".join(out)
    print(text)
    if a.out:
        rec = {
            "rows": rows, "games": len(games), "rows_with_void": rows_with_void, "bar": a.bar,
            "first_ply_by_kind": dict(n_first), "void_by_reason": dict(void_by_reason),
            "void_by_group": dict(void_by_group), "rescue_by_kind": dict(h_kind),
            "rescue_by_group_kind": {f"{g}:{k}": v for (g, k), v in h_kind_by_group.items()},
            "refusals": dict(refuse), "plans": dict(plans),
            "price": {"rescue_calls": resc_calls, "first_calls": first_calls, "rescue_ms": resc_ms, "first_ms": first_ms},
            "margins_best": {"n": len(margins_best), "mean": float(np.mean(margins_best)) if margins_best else None,
                             "ge_bar": int(sum(1 for m in margins_best if m >= a.bar)),
                             "ge_0": beats_best},
            "margins_nat": {"n": len(margins_nat), "mean": float(np.mean(margins_nat)) if margins_nat else None,
                            "ge_bar": int(sum(1 for m in margins_nat if m >= a.bar))},
            "windows_changed": win_changed, "windows_changed_by_applied": dict(win_changed_by_applied),
            "applied": dict(applied_census), "text": text,
        }
        with open(a.out, "w") as f:
            json.dump(rec, f, indent=1)
        print(f"[void_rescue_read] -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
