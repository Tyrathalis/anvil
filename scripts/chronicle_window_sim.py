"""Chronicle 1993-94 window: name-level and printing-level coverage by channel mix.

Design record: docs/design/collection-mode-sketch.md, "Completion round (2026-11-21)".
Reads the playable worktree (../forge-play): res/chronicle/releases.txt and res/editions.
Run: python3 scripts/chronicle_window_sim.py [info|market|till]
"""

import glob
import random
import re
import statistics as st
import sys
from pathlib import Path

FORK = str(Path(__file__).resolve().parents[2] / "forge-play/forge-gui/res") + "/"
ED = FORK + "editions/"
REL = [l.strip().split("|") for l in open(FORK + "chronicle/releases.txt") if l[0].isdigit()]
SLOTS = {
    "LEA": [("C", 11), ("U", 3), ("R", 1)],
    "ARN": [("C", 6), ("UR", 2)],
    "FEM": [("C", 5), ("U", 2), ("R", 1)],
}
for c in ("LEB", "2ED", "3ED", "LEG"):
    SLOTS[c] = SLOTS["LEA"]
for c in ("ATQ", "DRK"):
    SLOTS[c] = SLOTS["ARN"]
PRICE = {"C": 25, "U": 100, "R": 400}
sets = {}
for r in REL:
    code = r[1]
    f = [
        p
        for p in glob.glob(ED + "*.txt")
        if re.search(r"^Code=%s$" % re.escape(code), open(p, encoding="utf8").read(), re.M)
    ][0]
    pools = {"C": set(), "U": set(), "R": set()}
    on = False
    for l in open(f, encoding="utf8"):
        l = l.strip()
        if l.startswith("["):
            on = l == "[cards]"
            continue
        if on and l:
            m = re.match(r"\S+ (\w) (.+?)(?: @.*)?$", l)
            if m and m.group(1) in pools:
                pools[m.group(1)].add(m.group(2))
    P = {k: sorted(v) for k, v in pools.items()}
    P["UR"] = sorted(pools["U"] | pools["R"])
    sets[code] = dict(P=P, rel=int(r[4]), shelf=int(r[5]), price=int(r[6]))
ALL = set(n for s in sets.values() for k in "CUR" for n in s["P"][k])
NPRINT = sum(len(s["P"][k]) for s in sets.values() for k in "CUR")
if len(sys.argv) > 1 and sys.argv[1] == "info":
    for c, s in sets.items():
        print(c, {k: len(v) for k, v in s["P"].items()})
    print("names", len(ALL), "printings", NPRINT)
    sys.exit()
END = 70
START = 35


def run(
    rng,
    ration=2,
    cash=1000,
    spend="packs",
    wins=3,
    pick=1,
    horizon=1500,
    keep=None,
    spread=1.0,
    market=START,
):
    names = {}
    prints = set()
    out = {}
    money = 0
    credit = 0
    RAR = {n: r for s_ in sets.values() for r in "RUC" for n in s_["P"][r]}

    def add(c, n):
        names[n] = names.get(n, 0) + 1
        prints.add((c, n))

    def ev(c):
        return sum(
            k * sum(1 for n in sets[c]["P"][r] if n not in names) / len(sets[c]["P"][r])
            for r, k in SLOTS[c]
        )

    def openp(c):
        for r, k in SLOTS[c]:
            for n in rng.sample(sets[c]["P"][r], k):
                add(c, n)

    for d in range(horizon):
        inp = (
            [c for c, s in sets.items() if s["rel"] <= d < s["rel"] + s["shelf"]] if d < END else []
        )
        rel = [c for c, s in sets.items() if s["rel"] <= d]
        if d % 7 == 0:
            money += cash
        if inp:
            for _ in range(ration):
                openp(max(inp, key=ev))
            if spend == "packs":
                while True:
                    c = max(inp, key=lambda c: ev(c) / sets[c]["price"])
                    if money < sets[c]["price"]:
                        break
                    money -= sets[c]["price"]
                    openp(c)
        if keep and d >= market:
            for n, k in names.items():
                if k > keep:
                    credit += (k - keep) * PRICE[RAR[n]] * spread
                    names[n] = keep
        if d >= START:
            # sale proceeds (credit) buy singles only: at these prices a pack resells above its cost
            if spend == "singles" or d >= END:
                credit += money
                money = 0
            if credit >= PRICE["C"]:
                for r in "CUR":
                    miss = [(c, n) for c in rel for n in sets[c]["P"][r] if n not in names]
                    rng.shuffle(miss)
                    for c, n in miss:
                        if credit < PRICE[r]:
                            break
                        if n not in names:
                            credit -= PRICE[r]
                            add(c, n)
            for _ in range(wins):
                best = None
                bp = 0
                for c in rel:
                    for r in "CUR":
                        p = sum(1 for n in sets[c]["P"][r] if n not in names) / len(sets[c]["P"][r])
                        if p > bp:
                            bp = p
                            best = (c, r)
                if not best:
                    break
                c, r = best
                offer = rng.sample(sets[c]["P"][r], min(pick, len(sets[c]["P"][r])))
                new = [n for n in offer if n not in names]
                add(c, (new or offer)[0])
        if d == END - 1:
            out["n70"] = 100 * len(names) / len(ALL)
            out["p70"] = 100 * len(prints) / NPRINT
            out["per"] = {
                c: 100
                * sum(1 for k in "CUR" for n in sets[c]["P"][k] if n in names)
                / sum(len(sets[c]["P"][k]) for k in "CUR")
                for c in sets
            }
        for k, t in (("d90", 0.9), ("d100", 1)):
            if k not in out and len(names) >= t * len(ALL):
                out[k] = d + 1
        if "d100" in out and d >= END:
            break
    return out


# --- 'till' mode: period prices (Scrye 1995 medians, flat by rarity), a daily cap on what the shop
# buys from the player, commons unsellable, daily limits on packs and singles bought.
BUY = {"C": 25, "U": 100, "R": 300}
SELLR = {"C": 0.0, "U": 0.5, "R": 0.5}


def run_till(
    rng,
    till=500,
    keep=1,
    packlim=2,
    singlelim=3,
    market=7,
    ration=2,
    cash=1000,
    wins=3,
    pick=3,
    horizon=1500,
):
    cnt = {}
    out = {}
    money = 0
    RAR = {n: r for s_ in sets.values() for r in "RUC" for n in s_["P"][r]}

    def add(n):
        cnt[n] = cnt.get(n, 0) + 1

    def missfrac(c, r):
        return sum(1 for n in sets[c]["P"][r] if n not in cnt) / len(sets[c]["P"][r])

    def ev(c):
        return sum(k * missfrac(c, r) for r, k in SLOTS[c])

    def openp(c):
        for r, k in SLOTS[c]:
            for n in rng.sample(sets[c]["P"][r], k):
                add(n)

    for d in range(horizon):
        inp = (
            [c for c, s in sets.items() if s["rel"] <= d < s["rel"] + s["shelf"]] if d < END else []
        )
        rel = [c for c, s in sets.items() if s["rel"] <= d]
        if d % 7 == 0:
            money += cash
        for _ in range(ration if inp else 0):
            openp(max(inp, key=ev))
        if d >= market and till:
            room = till
            for n in sorted(
                (n for n, k in cnt.items() if k > keep and RAR[n] != "C"),
                key=lambda n: -BUY[RAR[n]],
            ):
                while cnt[n] > keep and room >= BUY[RAR[n]] * SELLR[RAR[n]]:
                    v = BUY[RAR[n]] * SELLR[RAR[n]]
                    room -= v
                    money += v
                    cnt[n] -= 1
        np_ = ns = 0
        while True:
            opts = []
            if inp and np_ < packlim:
                c = max(inp, key=lambda c: ev(c) / sets[c]["price"])
                if money >= sets[c]["price"]:
                    opts.append((ev(c) / sets[c]["price"], "p", c))
            if d >= market and ns < singlelim:
                for r in "CUR":
                    m = [n for c in rel for n in sets[c]["P"][r] if n not in cnt]
                    if m and money >= BUY[r]:
                        opts.append((1 / BUY[r], "s", rng.choice(m)))
                        break
            if not opts:
                break
            _, k, x = max(opts)
            if k == "p":
                money -= sets[x]["price"]
                openp(x)
                np_ += 1
            else:
                money -= BUY[RAR[x]]
                add(x)
                ns += 1
        if d >= START:
            for _ in range(wins):
                best = max(((missfrac(c, r), c, r) for c in rel for r in "CUR"), default=(0,))
                if not best[0]:
                    break
                offer = rng.sample(sets[best[1]]["P"][best[2]], pick)
                new = [n for n in offer if n not in cnt]
                add((new or offer)[0])
        if d == END - 1:
            out["n70"] = 100 * len(cnt) / len(ALL)
            out["bank"] = money / 100
        for k, t in (("d90", 0.9), ("d100", 1)):
            if k not in out and len(cnt) >= t * len(ALL):
                out[k] = d + 1
        if "d100" in out and d >= END:
            break
    return out


if len(sys.argv) > 1 and sys.argv[1] == "till":
    rng = random.Random(11)
    for name, kw in (
        [("no selling", dict(till=0))]
        + [
            (f"till ${t // 100}/day, keep {k}", dict(till=t, keep=k))
            for k in (1, 4)
            for t in (200, 500, 1000)
        ]
        + [
            ("till $5, keep 1, 6 singles/day", dict(singlelim=6)),
            ("till $5, keep 1, no tickets", dict(wins=0)),
            ("till $5, keep 1, market from day 35", dict(market=35)),
        ]
    ):
        rs = [run_till(rng, **kw) for _ in range(30)]
        m = lambda k: round(st.median(r.get(k, 9999) for r in rs))
        print(
            f"{name:40s} names@70 {m('n70')}%  d90 {m('d90')}  d100 {m('d100')}  cash@70 ${m('bank')}"
        )
    sys.exit()
rng = random.Random(7)
B = dict(pick=3)
if len(sys.argv) > 1 and sys.argv[1] == "market":
    cfgs = [("no selling", B)] + [
        (
            f"keep {k}, sell at {int(sp * 100)}% of buy, market day {m}",
            dict(B, keep=k, spread=sp, market=m),
        )
        for m in (35, 70)
        for k in (4, 1)
        for sp in (1.0, 0.5, 0.1)
    ]
else:
    cfgs = [
        ("ration 2 only", dict(cash=0, wins=0)),
        ("ration 2 + $10/wk packs", dict(wins=0)),
        ("+ 3 prize wins/day, random card", dict()),
        ("+ 3 prize wins/day, pick 1 of 3", dict(pick=3)),
        ("+ 2 prize wins/day, pick 1 of 3", dict(pick=3, wins=2)),
        ("+ 1 prize win/day, pick 1 of 3", dict(pick=3, wins=1)),
        ("$10/wk singles, 3 wins pick-of-3", dict(pick=3, spend="singles")),
        ("$30/wk singles, 3 wins pick-of-3", dict(pick=3, spend="singles", cash=3000)),
        ("ration 3, $10 packs, 3 wins pick-of-3", dict(pick=3, ration=3)),
        ("ration 4, $10 packs, 3 wins pick-of-3", dict(pick=3, ration=4)),
    ]
for name, kw in cfgs:
    rs = [run(rng, **kw) for _ in range(40)]
    m = lambda k: round(st.median(r.get(k, 9999) for r in rs))
    print(
        f"{name:42s} names@70 {m('n70')}%  printings@70 {m('p70')}%  d90 {m('d90')}  d100 {m('d100')}"
    )
    if name in ("ration 2 + $10/wk packs", "+ 3 prize wins/day, pick 1 of 3"):
        print("   per-set names@70:", {c: round(st.median(r["per"][c] for r in rs)) for c in sets})
