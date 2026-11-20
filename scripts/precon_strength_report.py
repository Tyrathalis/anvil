"""Per-deck strength from a heuristic mirror on the precon benchmark (ADR-0130, third addendum).

Reads a harness run in which both seats are the plain heuristic and every pair of decks is drawn
from a balanced schedule. Gives each deck's winrate, a Bradley-Terry rating fitted on all games
(so a deck's opponents are accounted for), the seat effect, and the means by era.

    uv run python scripts/precon_strength_report.py --run data/runs/pcmirror-<stamp> \
        --map data/benchmark/precons-178/deck-map.json --out data/benchmark/precons-178/strength.json
"""
import argparse
import json
import math
import os
import statistics as st


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args()
    dmap = json.load(open(a.map))
    keys = sorted(dmap)
    idx = {k: i for i, k in enumerate(keys)}
    n = len(keys)
    wins = [[0.0] * n for _ in range(n)]
    games = [0] * n
    won = [0.0] * n
    seat0 = total = draws = crashes = 0
    for line in open(os.path.join(a.run, "games.jsonl")):
        try:
            g = json.loads(line)
        except json.JSONDecodeError:
            continue
        d = [idx[os.path.basename(x)] for x in g["decks"]]
        if g["status"] != "won":
            draws += g["status"] == "draw"
            crashes += g["status"].startswith("crash")
            continue
        w = (g.get("winner") or "")
        s = 0 if w.startswith("Heur(1)") else 1 if w.startswith("Heur(2)") else None
        if s is None:
            continue
        total += 1
        seat0 += s == 0
        wins[d[s]][d[1 - s]] += 1
        for k in d:
            games[k] += 1
        won[d[s]] += 1

    # Bradley-Terry by minorization-maximization, with half a win against a phantom average deck as the prior
    p = [1.0] * n
    for _ in range(400):
        new = []
        for i in range(n):
            num = 0.5 + sum(wins[i])
            den = 1.0 / (p[i] + 1.0)
            for j in range(n):
                m = wins[i][j] + wins[j][i]
                if m:
                    den += m / (p[i] + p[j])
            new.append(num / den)
        gm = math.exp(st.fmean(math.log(x) for x in new))
        p = [x / gm for x in new]
    elo = [400 * math.log10(x) for x in p]

    rows = []
    for k in keys:
        i = idx[k]
        wr = won[i] / games[i] if games[i] else float("nan")
        rows.append({"deck": k, "name": dmap[k]["name"], "year": dmap[k]["year"], "games": games[i], "winrate": wr,
                     "se": math.sqrt(wr * (1 - wr) / games[i]) if games[i] else float("nan"), "rating": elo[i],
                     "unseen_share": dmap[k]["share"]})
    json.dump({"run": a.run, "games": total, "draws": draws, "crashes": crashes, "decks": rows}, open(a.out, "w"), indent=1)

    r = sorted(rows, key=lambda x: -x["rating"])
    print(f"{total} decided games, {draws} draws, {crashes} crashes; seat 0 wins {seat0 / total:.4f} ± {math.sqrt(.25 / total):.4f}")
    wr = [x["winrate"] for x in rows]
    print(f"deck winrate: {min(wr):.3f} to {max(wr):.3f}, standard deviation {st.pstdev(wr):.3f}; "
          f"sampling alone would give {math.sqrt(st.fmean(x['se'] ** 2 for x in rows)):.3f}; rating spread {st.pstdev(elo):.0f} (Elo scale)")
    print("\n| era | decks | mean winrate | mean rating |\n|---|---|---|---|")
    for lab, lo, hi in (("2011 to 2020", 0, 2021), ("2021 to 2023", 2021, 2024), ("2024 to 2026", 2024, 9999)):
        e = [x for x in rows if lo <= x["year"] < hi]
        print(f"| {lab} | {len(e)} | {st.fmean(x['winrate'] for x in e):.3f} | {st.fmean(x['rating'] for x in e):+.0f} |")
    xs, ys = [x["unseen_share"] for x in rows], [x["rating"] for x in rows]
    mx, my = st.fmean(xs), st.fmean(ys)
    cor = sum((u - mx) * (v - my) for u, v in zip(xs, ys)) / math.sqrt(sum((u - mx) ** 2 for u in xs) * sum((v - my) ** 2 for v in ys))
    print(f"\ncorrelation of rating with the deck's unseen share: {cor:+.2f}")
    for title, part in (("strongest", r[: a.top]), ("weakest", r[-a.top:])):
        print(f"\n| {title} | games | winrate | rating |\n|---|---|---|---|")
        for x in part:
            print(f"| {x['name']} | {x['games']} | {x['winrate']:.3f} ± {x['se']:.3f} | {x['rating']:+.0f} |")


if __name__ == "__main__":
    main()
