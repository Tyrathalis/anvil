"""Split a leaf-calibration read at the acting margin (the M13 search-ranking gate, step 0; a utility).

Re-reads the stored rows of a `prio_calibration.py` run (ADR-0106): the same searched windows
valued under a shallow leaf and under end rollouts. Per window it takes the candidates valued in
both arms. Windows are split by the shallow margin of the best option over the natural pick: at
or over the bar the search would have acted, under it it would not. Errors are a bootstrap over
games.

The headline is the pooled SLOPE of the end means on the shallow means, both centred per window:
how much of a shallow value difference between two options the outcome realizes. Rollout noise in
the truth widens its error and does not bias it. The per-window Spearman (ties averaged) is kept
beside it, with the truth's split-half ceiling: with a few rollouts per option the truth is flat
or tied in most windows, so the Spearman has almost no power and is not a gate statistic.
`prio_calibration.py`'s own Spearman ranks ties by position, which reads tied options as agreeing
(ADR-0106's 11-17 addendum).

    uv run python scripts/search_rank_split.py --shallow next=<s0>,<s1> --truth end=<s0>,<s1> --out split.json

`--live <dir>[,<dir>...]` reads one run instead, whose search rows carry both sides: the shallow
option values and a deep round of end rollouts on the natural pick plus the top options
(`-searchdeep B -searchdeepleaf end -searchdeepfloor 1.0`, `-searchdeeplo` at the bar and
`-searchdeepbar` over 1 so nothing acts). The candidates are the deep set.

    uv run python scripts/search_rank_split.py --live <s0>,<s1> --out live.json
"""
import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

sys.path.insert(0, str(Path(__file__).parent))
from prio_calibration import GOOD_KINDS, load_arm, mean_value  # noqa: E402


def rho(x, y):
    """Spearman with averaged ties; None when either side is constant."""
    rx, ry = rankdata(x), rankdata(y)
    if np.std(rx) == 0 or np.std(ry) == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def half_means(o: dict):
    vs = [v for v, k in zip(o["v"], o["kind"]) if v is not None and k in GOOD_KINDS]
    if len(vs) < 2:
        return None
    h = len(vs) // 2
    return sum(vs[:h]) / h, sum(vs[h:]) / (len(vs) - h)


def boot(rows, key, rng, n=2000):
    """Mean of rows[key] (None skipped) with a bootstrap over games; None counted as 0 under key+'0'."""
    by_game = {}
    for r in rows:
        if r.get(key) is not None:
            by_game.setdefault(r["seed"], []).append(r[key])
    if not by_game:
        return None
    games = [np.array(v) for v in by_game.values()]
    sums = np.array([g.sum() for g in games])
    cnts = np.array([len(g) for g in games])
    idx = rng.integers(0, len(games), size=(n, len(games)))
    means = sums[idx].sum(1) / cnts[idx].sum(1)
    return {"mean": float(sums.sum() / cnts.sum()), "se": float(means.std()), "windows": int(cnts.sum()),
            "games": len(games)}


def slope(rows, rng, n=2000):
    """Pooled slope of truth on shallow, centred per window; bootstrap over games."""
    by_game = {}
    for r in rows:
        g = by_game.setdefault(r["seed"], [0.0, 0.0])
        g[0] += r["sxy"]
        g[1] += r["sxx"]
    arr = np.array(list(by_game.values()))
    if len(arr) < 2 or arr[:, 1].sum() == 0:
        return None
    idx = rng.integers(0, len(arr), size=(n, len(arr)))
    b = arr[idx, 0].sum(1) / arr[idx, 1].sum(1)
    return {"slope": float(arr[:, 0].sum() / arr[:, 1].sum()), "se": float(b.std()),
            "shallow_sumsq": float(arr[:, 1].sum()), "windows": len(rows), "games": len(arr)}


def live_windows(dirs):
    """Yield (seed, shallow means, truth means, natural's position, truth half-means) per deep-round window."""
    for d in dirs:
        for f in sorted(glob.glob(str(Path(d) / "workers" / "*" / "labels.jsonl"))):
            for ln in open(f):
                if not ln.startswith('{"ev":"search"'):
                    continue
                r = json.loads(ln)
                deep = r.get("deep") or {}
                if deep.get("by") not in ("floor", "band") or not deep.get("copies"):
                    continue
                labels = [o["label"] for o in r["opts"]]
                nat = labels.index(r["nat"]) if r["nat"] in labels else -1
                s, t, halves, nat_pos = [], [], [], -1
                for cp in deep["copies"]:
                    o = cp["o"]
                    sm, tm = mean_value(r["opts"][o]), mean_value(cp)
                    if sm is None or tm is None:
                        continue
                    if o == nat:
                        nat_pos = len(s)
                    s.append(sm)
                    t.append(tm)
                    halves.append(half_means(cp))
                yield int(r["seed"]), s, t, nat_pos, halves


def pair_windows(sw, tw):
    for k in sorted(set(sw) & set(tw)):
        so, to = sw[k]["opts"], tw[k]["opts"]
        if [o["label"] for o in so] != [o["label"] for o in to] or sw[k]["nat"] != tw[k]["nat"]:
            continue
        cands = [i for i in range(len(so)) if mean_value(so[i]) is not None and mean_value(to[i]) is not None]
        labels = [o["label"] for o in so]
        nat = labels.index(sw[k]["nat"]) if sw[k]["nat"] in labels else -1
        yield (k[0], [mean_value(so[i]) for i in cands], [mean_value(to[i]) for i in cands],
               cands.index(nat) if nat in cands else -1, [half_means(to[i]) for i in cands])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shallow", help="leaf=dir[,dir...]")
    ap.add_argument("--truth", help="leaf=dir[,dir...]")
    ap.add_argument("--live", help="dir[,dir...]: one run whose rows carry a deep end round")
    ap.add_argument("--bar", type=float, default=0.10)
    ap.add_argument("--min-cands", type=int, default=3)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    if a.live:
        sh, tr = "next", "end (deep round)"
        windows = live_windows([d for d in a.live.split(",") if d])
    else:
        arms = {}
        for spec in (a.shallow, a.truth):
            leaf, _, dirs = spec.partition("=")
            arms[leaf] = load_arm([Path(d) for d in dirs.split(",") if d], Counter())
        (sh, sw), (tr, tw) = arms.items()
        windows = pair_windows(sw, tw)

    rows = []
    for seed, s, t, nat_pos, halves in windows:
        if len(s) < 2 or nat_pos < 0:
            continue
        margin = max(s) - s[nat_pos]
        sc, tc = np.array(s) - np.mean(s), np.array(t) - np.mean(t)
        ranked = len(s) >= a.min_cands
        r = rho(s, t) if ranked else None
        ceil = rho([h[0] for h in halves], [h[1] for h in halves]) if ranked and all(halves) else None
        am = int(np.argmax(s))
        rows.append({
            "seed": seed, "margin": margin, "acted": margin >= a.bar, "n": len(s),
            "sxy": float(sc @ tc), "sxx": float(sc @ sc),
            "rho": r, "truth_flat": 1.0 if np.std(t) == 0 else 0.0, "ceil": ceil,
            "top_hit": 1.0 if t[am] >= max(t) else 0.0,
            "chance_hit": float(np.mean([x >= max(t) for x in t])),
            "gain": t[am] - t[nat_pos],
        })

    rng = np.random.default_rng(0)
    out = {"shallow": sh, "truth": tr, "bar": a.bar, "min_cands": a.min_cands, "windows": len(rows), "groups": {}}
    groups = {"all": rows, "acted": [r for r in rows if r["acted"]], "un-acted": [r for r in rows if not r["acted"]],
              "un-acted, margin 0": [r for r in rows if r["margin"] <= 0],
              "un-acted, margin 0 to bar": [r for r in rows if 0 < r["margin"] < a.bar]}
    print(f"{sh} against {tr}; bar {a.bar}; windows with >= 2 candidates valued in both: {len(rows)}")
    for name, g in groups.items():
        rec = {key: boot(g, key, rng) for key in
               ("rho", "ceil", "truth_flat", "top_hit", "chance_hit", "gain", "n")}
        sl = slope(g, rng)
        out["groups"][name] = {**rec, "slope": sl}
        print(f"  {name}: {len(g)} windows")
        if sl:
            print(f"      slope       {sl['slope']:+.4f} ± {sl['se']:.4f}  (shallow sum of squares {sl['shallow_sumsq']:.2f})")
        for key, v in rec.items():
            if v:
                print(f"      {key:11s} {v['mean']:+.4f} ± {v['se']:.4f}  ({v['windows']} windows, {v['games']} games)")
    if a.out:
        json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
