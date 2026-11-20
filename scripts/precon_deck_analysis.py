"""Deck analysis on the precon benchmark's heuristic mirror (docs/design/precon-deck-analysis.md).

Takes the per-deck ratings of scripts/precon_strength_report.py and adds: each deck's color
identity (the colors in its cards' mana costs), strength by color and by color count, the trend by
release year with the decks furthest from it, and, given a one-turn replay of the mirror's seeds
with the census log, the first player's edge.

    uv run python scripts/precon_deck_analysis.py --strength data/benchmark/precons-178/strength.json \
        --decks data/benchmark/precons-178/decks --mirror data/runs/pcmirror-<stamp> \
        --starters data/runs/pcfirstcap-<stamp> > data/benchmark/precons-178/analysis.md

Everything here is strength in the plain heuristic's hands, two-player. It is exploratory.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import os
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ORDER = "WUBRG"
NAMES = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}


def fit(xs: list[float], ys: list[float]) -> tuple[float, float, float, float, list[float]]:
    """Least squares y = a + b x: (a, b, the slope's standard error, R squared, residuals)."""
    mx, my = st.fmean(xs), st.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    res = [y - (a + b * x) for x, y in zip(xs, ys)]
    se = math.sqrt(sum(r * r for r in res) / (len(xs) - 2) / sxx)
    return a, b, se, 1 - sum(r * r for r in res) / sum((y - my) ** 2 for y in ys), res


def mean_se(xs: list[int]) -> str:
    p = st.fmean(xs)
    return f"{p:.4f} ± {math.sqrt(p * (1 - p) / len(xs)):.4f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--strength", required=True)
    ap.add_argument("--decks", required=True)
    ap.add_argument("--mirror", help="the mirror's run directory (for the first-player join)")
    ap.add_argument("--starters", help="a -turncap 1 --census replay of the mirror's seeds")
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args()

    from precon_benchmark_decks import BASICS, cards

    from anvil.encoder.cardtext import _scan_files, normalize

    files = _scan_files()
    cache: dict[str, set[str]] = {}

    def colors_of(name: str) -> set[str]:
        if name not in cache:
            c: set[str] = set()
            p = files.get(normalize(name.split(" // ")[0]))
            if p:
                for line in open(p, encoding="utf-8", errors="replace"):
                    if line.startswith("ManaCost:"):
                        c |= set(re.findall(r"[WUBRG]", line[9:]))
            cache[name] = c
        return cache[name]

    S = json.load(open(a.strength))["decks"]
    for d in S:
        cmd, main_ = cards(Path(a.decks) / d["deck"])
        ci: set[str] = set()
        for c in cmd + main_:
            if c not in BASICS:
                ci |= colors_of(c)
        d["colors"] = "".join(x for x in ORDER if x in ci) or "C"
    by_deck = {d["deck"]: d for d in S}

    xs, ys = [d["year"] for d in S], [d["rating"] for d in S]
    _, b, se, r2, res = fit(xs, ys)
    _, bw, sew, _, _ = fit(xs, [d["winrate"] for d in S])
    for d, r in zip(S, res):
        d["above_trend"] = r
    print(f"## The trend by release year\n\n{b:+.1f} ± {se:.1f} rating points a year (R² {r2:.2f}); "
          f"winrate {100 * bw:+.2f} ± {100 * sew:.2f}pp a year.\n")
    print("| Year | Decks | Mean winrate | Mean rating | Best | Worst |\n|---|---|---|---|---|---|")
    for y in sorted(set(xs)):
        e = sorted((d for d in S if d["year"] == y), key=lambda d: d["rating"])
        print(f"| {y} | {len(e)} | {st.fmean(d['winrate'] for d in e):.3f} | {st.fmean(d['rating'] for d in e):+.0f} "
              f"| {e[-1]['name']} ({e[-1]['winrate']:.2f}) | {e[0]['name']} ({e[0]['winrate']:.2f}) |")

    print("\n## Colors\n\n| Color | Decks with it | Mean winrate | Rating against decks without it, year trend removed |\n|---|---|---|---|")
    for c in ORDER:
        w = [d for d in S if c in d["colors"]]
        wo = [d for d in S if c not in d["colors"]]
        diff = st.fmean(d["above_trend"] for d in w) - st.fmean(d["above_trend"] for d in wo)
        sed = math.sqrt(st.pvariance([d["above_trend"] for d in w]) / len(w) + st.pvariance([d["above_trend"] for d in wo]) / len(wo))
        print(f"| {NAMES[c]} | {len(w)} | {st.fmean(d['winrate'] for d in w):.3f} | {diff:+.0f} ± {sed:.0f} |")
    print("\n| Colors in the deck | Decks | Mean winrate | Mean rating |\n|---|---|---|---|")
    for n in sorted({len(d["colors"]) for d in S}):
        e = [d for d in S if len(d["colors"]) == n]
        print(f"| {n} | {len(e)} | {st.fmean(d['winrate'] for d in e):.3f} | {st.fmean(d['rating'] for d in e):+.0f} |")
    combos = collections.defaultdict(list)
    for d in S:
        combos[d["colors"]].append(d)
    print("\n| Combination | Decks | Mean winrate | Mean rating | Years |\n|---|---|---|---|---|")
    for k, e in sorted(combos.items(), key=lambda kv: -st.fmean(d["rating"] for d in kv[1])):
        print(f"| {k} | {len(e)} | {st.fmean(d['winrate'] for d in e):.3f} | {st.fmean(d['rating'] for d in e):+.0f} "
              f"| {min(d['year'] for d in e)} to {max(d['year'] for d in e)} |")

    r = sorted(S, key=lambda d: -d["above_trend"])
    for title, part in (("Furthest above their year's trend", r[: a.top]), ("Furthest below", r[-a.top:][::-1])):
        print(f"\n## {title}\n\n| Deck | Colors | Winrate | Rating | Against the trend |\n|---|---|---|---|---|")
        for d in part:
            print(f"| {d['name']} | {d['colors']} | {d['winrate']:.3f} | {d['rating']:+.0f} | {d['above_trend']:+.0f} |")

    if a.mirror and a.starters:
        start: dict[int, int] = {}
        for w in glob.glob(os.path.join(a.starters, "workers", "*")):
            gs = [json.loads(line) for line in open(os.path.join(w, "games.jsonl"))]
            who = [json.loads(line)["p"] for line in open(os.path.join(w, "census.jsonl")) if '"chooseStartingPlayer"' in line]
            if len(gs) == len(who):
                for g, p in zip(gs, who):
                    start[g["i"]] = 0 if p.startswith("Heur(1)") else 1
        rows = []
        per: dict[str, list[list[int]]] = collections.defaultdict(lambda: [[0, 0], [0, 0]])
        for line in open(os.path.join(a.mirror, "games.jsonl")):
            g = json.loads(line)
            if g["status"] != "won" or g["i"] not in start:
                continue
            w = 0 if g["winner"].startswith("Heur(1)") else 1
            f = start[g["i"]]
            dk = [os.path.basename(x) for x in g["decks"]]
            exp = 1 / (1 + 10 ** ((by_deck[dk[1 - f]]["rating"] - by_deck[dk[f]]["rating"]) / 400))
            rows.append((int(w == f), exp, by_deck[dk[f]]["rating"], by_deck[dk[1 - f]]["rating"]))
            for seat in (0, 1):
                side = 0 if seat == f else 1
                per[dk[seat]][side][0] += int(w == seat)
                per[dk[seat]][side][1] += 1
        print(f"\n## Going first\n\nThe first player wins {mean_se([x[0] for x in rows])} of {len(rows)} decided games; "
              f"the decks alone predict {st.fmean(x[1] for x in rows):.4f}.\n")
        cut = sorted(d["rating"] for d in S)
        lo, hi = cut[len(cut) // 3], cut[2 * len(cut) // 3]
        print("| The first player's deck, by rating | Games | First player wins | Decks alone | Edge |\n|---|---|---|---|---|")
        for lab, x0, x1 in (("weakest third", -1e9, lo), ("middle third", lo, hi), ("strongest third", hi, 1e9)):
            e = [x for x in rows if x0 <= x[2] < x1]
            print(f"| {lab} | {len(e)} | {mean_se([x[0] for x in e])} | {st.fmean(x[1] for x in e):.4f} "
                  f"| {100 * (st.fmean(x[0] for x in e) - st.fmean(x[1] for x in e)):+.1f}pp |")
        print("\n| Both decks, by rating | Games | First player wins | Decks alone | Edge |\n|---|---|---|---|---|")
        for lab, test in (("both in the weakest third", lambda x: x[2] < lo and x[3] < lo),
                          ("both in the strongest third", lambda x: x[2] >= hi and x[3] >= hi)):
            e = [x for x in rows if test(x)]
            print(f"| {lab} | {len(e)} | {mean_se([x[0] for x in e])} | {st.fmean(x[1] for x in e):.4f} "
                  f"| {100 * (st.fmean(x[0] for x in e) - st.fmean(x[1] for x in e)):+.1f}pp |")
        gaps = []
        for k, ((pw, pn), (dw, dn)) in per.items():
            if pn >= 60 and dn >= 60:
                p, q = pw / pn, dw / dn
                gaps.append((p - q, math.sqrt(p * (1 - p) / pn + q * (1 - q) / dn), by_deck[k]))
        g_, r_ = [x[0] for x in gaps], [x[2]["rating"] for x in gaps]
        _, gb, gse, _, _ = fit(r_, g_)
        print(f"\nPer deck, winrate on the play minus on the draw: mean {st.fmean(g_):+.3f}; standard deviation across decks "
              f"{st.pstdev(g_):.3f}, where sampling alone gives {math.sqrt(st.fmean(x[1] ** 2 for x in gaps)):.3f}. "
              f"Its slope on the deck's rating is {1000 * gb:+.2f} ± {1000 * gse:.2f}pp per 10 rating points.")
        d["play_minus_draw"] = None
        for gap, _, deck in gaps:
            deck["play_minus_draw"] = gap
    json.dump(S, open(os.path.join(os.path.dirname(a.strength), "deck-analysis.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
