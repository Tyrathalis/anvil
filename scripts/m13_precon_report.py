"""Read the held-out precon arms (M13 Build 0 step 5, ADR-0130; the driver is scripts/m13_precon.sh).

    uv run python scripts/m13_precon_report.py --out data/runs/m13-precon/read --map data/runs/m13-precon/deck-map.json

Per arm: the model's winrate against the plain heuristic (a win over all games, as in arms_report.py).
Between arms: the paired difference on (seat, game index). Within the arms: the winrate by the share
of the model's own deck that is outside the checkpoint's pool, by the opponent deck's share, and by
the deck's release year.
"""
import argparse
import json
import math
import os
import statistics as st


def load(done: str) -> dict:
    """{(seat, i): game row + 'win' + 'mine' / 'theirs' (deck file names)} for one arm's two seat runs."""
    out = {}
    for rd in open(done).read().strip().split(","):
        seat = int(str(json.load(open(f"{rd}/run.json"))["bridge_seats"]).strip("[]"))
        for line in open(f"{rd}/games.jsonl"):
            g = json.loads(line)
            g["win"] = 1 if (g.get("winner") or "").startswith("Anvil") else 0
            g["mine"], g["theirs"] = (os.path.basename(g["decks"][seat]), os.path.basename(g["decks"][1 - seat]))
            out[(seat, g["i"])] = g
    return out


def ms(xs: list[float]) -> str:
    if not xs:
        return "-"
    m = st.fmean(xs)
    se = math.sqrt(st.pvariance(xs) / len(xs)) if len(xs) > 1 else float("nan")
    return f"{m:.4f} ± {se:.4f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--map", required=True)
    a = ap.parse_args()
    dmap = json.load(open(a.map))
    arms = {t: load(f"{a.out}/{t}.done") for t in ("asis", "idnull", "idmean") if os.path.isfile(f"{a.out}/{t}.done")}

    print("| arm | games | model winrate | seat 0 | seat 1 | draws | crashes | game s, median / mean |")
    print("|---|---|---|---|---|---|---|---|")
    for t, g in arms.items():
        v = list(g.values())
        secs = [x["ms"] / 1000 for x in v]
        print(f"| {t} | {len(v)} | **{ms([x['win'] for x in v])}** | {ms([x['win'] for k, x in g.items() if k[0] == 0])} "
              f"| {ms([x['win'] for k, x in g.items() if k[0] == 1])} | {sum(x['status'] == 'draw' for x in v)} "
              f"| {sum(x['status'].startswith('crash') for x in v)} | {st.median(secs):.1f} / {st.fmean(secs):.1f} |")

    print("\n| paired on seat and seed | difference | pairs | up / down |")
    print("|---|---|---|---|")
    names = list(arms)
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            d = [arms[y][k]["win"] - arms[x][k]["win"] for k in arms[x] if k in arms[y]]
            m, se = st.fmean(d), math.sqrt(st.pvariance(d) / len(d))
            print(f"| {y} − {x} | {m * 100:+.2f} ± {se * 100:.2f}pp | {len(d)} | {sum(v > 0 for v in d)} / {sum(v < 0 for v in d)} |")

    def split(title: str, key, cuts: list[tuple[str, float, float]]) -> None:
        print(f"\n| {title} | " + " | ".join(arms) + " | games per arm |")
        print("|---|" + "---|" * (len(arms) + 1))
        for label, lo, hi in cuts:
            cells, n = [], 0
            for g in arms.values():
                w = [x["win"] for x in g.values() if lo <= key(x) < hi]
                cells.append(ms(w))
                n = len(w)
            print(f"| {label} | " + " | ".join(cells) + f" | {n} |")

    shares = sorted(d["share"] for d in dmap.values())
    q1, q2 = shares[len(shares) // 3], shares[2 * len(shares) // 3]
    thirds = [(f"under {q1:.0%}", 0, q1), (f"{q1:.0%} to {q2:.0%}", q1, q2), (f"{q2:.0%} and over", q2, 2)]
    split("unseen share of the model's deck", lambda x: dmap[x["mine"]]["share"], thirds)
    split("unseen share of the opponent's deck", lambda x: dmap[x["theirs"]]["share"], thirds)
    eras = [("2011 to 2020", 0, 2021), ("2021 to 2023", 2021, 2024), ("2024 to 2026", 2024, 9999)]
    split("release year of the model's deck", lambda x: dmap[x["mine"]]["year"] or 0, eras)


if __name__ == "__main__":
    main()
