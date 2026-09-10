#!/usr/bin/env python3
"""pay_calibration — the payment target's horizon calibration read
(ADR-0105 evening 4 close; m12-plan Build 3).

The set-keyed pay head learned its target — the END-OF-TURN one-ply leaf
value per goal — and its deviations leaned against the outcome (6 up / 12
down at argmax). This read asks whether that target ranks payments the way
a rollout does, on heuristic games: the same searched windows (the search
directive observational, the pay slot ON) under three pay leaves, each arm
a final_read pair of seat runs on the same pairs + seed base:

  eot   the target: the seat's first quiescent window of a later turn,
        valued by the head (rolls = leaf noise)
  h2    the certify horizon: the first quiescent window of a turn > t+2,
        valued by the head, + the certify axes snapshot at the stop
  end   the copy played to its natural end: the outcome (1 / 0.5 / 0),
        paired across answers by roll seed

The mainline is byte-identical across arms (search never acts; copies are
RNG-neutral), so sub rows join by (seed, t, sw, seat, o, ord, a) and the
join rate is itself the identity proof (reported; < 100% = investigate).

Per (window, goal ≠ auto): d_leaf = v(goal) − v(auto) under each leaf.
Read (pooled over pairs):
  * Spearman ρ of d_eot vs d_end (the calibration), d_h2 vs d_end, d_eot vs
    d_h2, and d_eot vs the h2 axes score (life + development vs auto).
  * CONVERSION at bars 0.01 / 0.03 / 0.05: on windows where the eot leaf
    prefers some goal over auto by ≥ bar (the pool's positives), the mean
    d_end of the eot-best goal ± SE and its sign split — the number the
    head's serve rule needs: > 0 = the target converts (the lean was noise),
    ≤ 0 = the target is myopic on payments (change it: h2 / the outcome).
    The same keyed on the h2 leaf, and the oracle (best-by-end) as the
    ceiling.
  * Ties (max d_eot < bar): mean d_end of the eot-best goal (≈ 0 expected).
  * Per arm: windows, answers, copy kinds (leaf / end / draw / timeout /
    crash), leaf noise (roll SD), copy wall per answer (rollout arms).

Usage:
  pay_calibration.py --arm eot=dirS0,dirS1 --arm h2=... --arm end=... --out read.json
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

BARS = (0.01, 0.03, 0.05)
GOOD_KINDS = {"leaf", "end", "draw"}


def _label_files(run: Path):
    return sorted(glob.glob(str(run / "workers" / "*" / "labels.jsonl"))) or sorted(
        glob.glob(str(run / "labels*.jsonl"))
    )


def load_arm(dirs: list[Path], counts: Counter) -> dict:
    """window key -> {answers: {a: {v: [..], kind: [..], snap: [..]|None, ms}},
    n, nat, label, opts: [labels]}"""
    out = {}
    for d in dirs:
        for f in _label_files(d):
            for ln in open(f):
                if not ln.startswith('{"ev":"search"'):
                    continue
                try:
                    r = json.loads(ln)
                except json.JSONDecodeError:
                    counts["bad_json"] += 1
                    continue
                counts["search_rows"] += 1
                opts = [o.get("label") for o in r.get("opts") or []]
                for s in r.get("sub") or []:
                    if s.get("kind") != "pay":
                        continue
                    key = (int(r["seed"]), int(r["t"]), int(r["sw"]), int(r["seat"]), int(s["o"]), int(s.get("ord", 0)))
                    counts["pay_sub"] += 1
                    ans = {}
                    for a in s.get("ans") or []:
                        idx = a.get("a") or []
                        if len(idx) != 1:
                            continue
                        ans[int(idx[0])] = {
                            "v": list(a.get("v") or []),
                            "kind": list(a.get("kind") or []),
                            "snap": a.get("snap"),
                            "ms": a.get("ms"),
                        }
                    if key in out:
                        counts["dup_key"] += 1
                    out[key] = {
                        "answers": ans,
                        "n": int(s.get("n", 0)),
                        "nat": list(s.get("nat") or []),
                        "label": s.get("label"),
                        "leaf": s.get("leaf"),
                        "opts": opts,
                        "seat": int(r["seat"]),
                    }
    return out


def mean_value(a: dict) -> float | None:
    vs = [v for v, k in zip(a["v"], a["kind"]) if v is not None and k in GOOD_KINDS]
    return sum(vs) / len(vs) if vs else None


def roll_sd(a: dict) -> float | None:
    vs = [v for v, k in zip(a["v"], a["kind"]) if v is not None and k in GOOD_KINDS]
    return st.pstdev(vs) if len(vs) >= 2 else None


def axes_score(snap_goal, snap_auto, seat: int) -> float | None:
    """The M9 certify's generic score at the stop: life diff + development
    (creatures + lands − hand) of the payer, goal minus auto, both rolls
    paired by index. None when either side is missing."""
    if not snap_goal or not snap_auto:
        return None
    vals = []
    for g, a in zip(snap_goal, snap_auto):
        if not g or not a:
            continue
        o = 1 - seat
        # [t_end, ended, life0, life1, cre0, cre1, pow0, pow1, hand0, hand1, land0, land1]
        def ax(s):
            life = s[2 + seat] - s[2 + o]
            dev = s[4 + seat] + s[10 + seat] - s[8 + seat]
            return life + dev
        vals.append(ax(g) - ax(a))
    return sum(vals) / len(vals) if vals else None


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3:
        return None
    xr = np.argsort(np.argsort(x)).astype(float)
    yr = np.argsort(np.argsort(y)).astype(float)
    # ties: average ranks
    def avg_rank(v):
        v = np.asarray(v)
        order = np.argsort(v, kind="mergesort")
        ranks = np.empty(len(v))
        sv = v[order]
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and sv[j + 1] == sv[i]:
                j += 1
            ranks[order[i : j + 1]] = (i + j) / 2.0
            i = j + 1
        return ranks
    xr, yr = avg_rank(x), avg_rank(y)
    if xr.std() == 0 or yr.std() == 0:
        return None
    return float(np.corrcoef(xr, yr)[0, 1])


def mean_se(v: list[float]) -> tuple[float | None, float | None]:
    if not v:
        return None, None
    m = sum(v) / len(v)
    se = (st.pstdev(v) / math.sqrt(len(v))) if len(v) > 1 else None
    return m, se


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", action="append", required=True, help="name=dir[,dir] (eot | h2 | end | ...)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    arms: dict[str, dict] = {}
    counts: dict[str, Counter] = {}
    for spec in a.arm:
        name, dirs = spec.split("=", 1)
        c = Counter()
        arms[name] = load_arm([Path(d) for d in dirs.split(",")], c)
        counts[name] = c
    names = list(arms)
    ref = names[0]
    report: dict = {"arms": {}, "join": {}, "pairs": {}, "conversion": {}, "ties": {}}

    # ---- per-arm telemetry
    for name, wins in arms.items():
        kinds = Counter()
        sds, ms = [], []
        n_ans = 0
        for w in wins.values():
            for ans in w["answers"].values():
                n_ans += 1
                kinds.update(k for k in ans["kind"] if k)
                sd = roll_sd(ans)
                if sd is not None:
                    sds.append(sd)
                if ans.get("ms") is not None:
                    ms.append(ans["ms"])
        report["arms"][name] = {
            "windows": len(wins),
            "answers": n_ans,
            "copy_kinds": dict(kinds),
            "roll_sd_mean": (sum(sds) / len(sds)) if sds else None,
            "ms_per_answer_mean": (sum(ms) / len(ms)) if ms else None,
            "ms_per_answer_p90": (sorted(ms)[int(0.9 * (len(ms) - 1))] if ms else None),
            "counts": dict(counts[name]),
        }

    # ---- the join (identity across arms)
    keys = set(arms[ref])
    for name in names[1:]:
        keys &= set(arms[name])
    ident_ok = 0
    ident_bad = 0
    for k in keys:
        w0 = arms[ref][k]
        same = all(
            arms[n][k]["n"] == w0["n"] and arms[n][k]["label"] == w0["label"]
            and arms[n][k]["opts"] == w0["opts"] for n in names[1:]
        )
        ident_ok += same
        ident_bad += not same
    # coverage: a horizon-leaf arm clips long games at the clock (their late
    # windows are lost), so windows present in the ref arm but absent from a
    # rollout arm concentrate late — report the loss by turn bucket
    def by_turn(ks):
        c = Counter()
        for k in ks:
            c[f"t{(k[1] - 1) // 5 * 5 + 1:02d}"] += 1
        return dict(sorted(c.items()))
    ref_only = {n: set(arms[ref]) - set(arms[n]) for n in names[1:]}
    report["join"] = {
        "windows_per_arm": {n: len(arms[n]) for n in names},
        "joined": len(keys),
        "identical_window": ident_ok,
        "mismatched_window": ident_bad,
        "joined_by_turn": by_turn(keys),
        "ref_only_by_turn": {n: by_turn(ks) for n, ks in ref_only.items()},
        "ref_only": {n: len(ks) for n, ks in ref_only.items()},
    }

    # ---- per (window, goal) deltas
    rows = []  # {key, a, d_<arm>..., axes_h2, axes_end}
    for k in keys:
        w0 = arms[ref][k]
        seat = w0["seat"]
        for goal in w0["answers"]:
            if goal == 0:
                continue
            row = {"key": k, "a": goal}
            ok = True
            for n in names:
                w = arms[n][k]
                if 0 not in w["answers"] or goal not in w["answers"]:
                    ok = False
                    break
                v0 = mean_value(w["answers"][0])
                vg = mean_value(w["answers"][goal])
                if v0 is None or vg is None:
                    ok = False
                    break
                row["d_" + n] = vg - v0
                row["ax_" + n] = axes_score(w["answers"][goal].get("snap"), w["answers"][0].get("snap"), seat)
            if ok:
                rows.append(row)
    report["pairs"]["n"] = len(rows)

    def col(n):
        return [r["d_" + n] for r in rows]

    corr = {}
    for i, n1 in enumerate(names):
        for n2 in names[i + 1 :]:
            corr[f"{n1}_vs_{n2}"] = spearman(col(n1), col(n2))
    for n in names:
        ax = [(r["d_" + ref], r["ax_" + n]) for r in rows if r.get("ax_" + n) is not None]
        if ax:
            corr[f"{ref}_vs_axes_{n}"] = spearman([x for x, _ in ax], [y for _, y in ax])
            corr[f"n_axes_{n}"] = len(ax)
    report["pairs"]["spearman"] = corr

    # ---- conversion: the leaf's best goal per window vs the rollout
    by_win: dict[tuple, list] = defaultdict(list)
    for r in rows:
        by_win[r["key"]].append(r)
    conv: dict = {}
    for picker in names:  # the leaf that picks
        for target in names:  # the leaf that judges
            if picker == target:
                continue
            for bar in BARS:
                pos, tie = [], []
                pos_ax = []
                for k, rs in by_win.items():
                    best = max(rs, key=lambda r: r["d_" + picker])
                    if best["d_" + picker] >= bar:
                        pos.append(best["d_" + target])
                        if best.get("ax_" + target) is not None:
                            pos_ax.append(best["ax_" + target])
                    else:
                        tie.append(best["d_" + target])
                m, se = mean_se(pos)
                mt, _ = mean_se(tie)
                conv[f"{picker}->{target}@{bar}"] = {
                    "positives": len(pos),
                    "mean_d": m,
                    "se": se,
                    "t": (m / se) if (m is not None and se) else None,
                    "up": sum(1 for v in pos if v > 0),
                    "flat": sum(1 for v in pos if v == 0),
                    "down": sum(1 for v in pos if v < 0),
                    "ties": len(tie),
                    "ties_mean_d": mt,
                    "axes_mean": (sum(pos_ax) / len(pos_ax)) if pos_ax else None,
                }
    report["conversion"] = conv

    # ---- the oracle ceiling: the best goal by each arm judged by itself
    oracle = {}
    for n in names:
        vals = [max(r["d_" + n] for r in rs) for rs in by_win.values()]
        pos = [v for v in vals if v > 0]
        oracle[n] = {"windows": len(vals), "best_positive": len(pos), "mean_best": (sum(vals) / len(vals)) if vals else None}
    report["oracle"] = oracle

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(report, f, indent=1, default=float)

    # ---- the summary
    print(f"pay_calibration: arms {names}; joined windows {len(keys)} "
          f"(identical {ident_ok} / mismatched {ident_bad}); (window, goal) pairs {len(rows)}")
    print(f"  windows per arm {report['join']['windows_per_arm']}; in {ref} only: {report['join']['ref_only']}"
          f" — by turn {report['join']['ref_only_by_turn']}")
    for n in names:
        t = report["arms"][n]
        print(f"  {n:<5} windows {t['windows']:>5} answers {t['answers']:>6} kinds {t['copy_kinds']} "
              f"roll_sd {t['roll_sd_mean'] if t['roll_sd_mean'] is None else round(t['roll_sd_mean'], 4)} "
              f"ms/answer {t['ms_per_answer_mean'] if t['ms_per_answer_mean'] is None else int(t['ms_per_answer_mean'])}")
    print("  spearman:", {k: (None if v is None else round(v, 3)) for k, v in corr.items()})
    for k, v in conv.items():
        if v["positives"] == 0:
            continue
        print(f"  {k:<16} n {v['positives']:>4}  mean_d {v['mean_d']:+.4f} ± {v['se'] if v['se'] is None else round(v['se'], 4)}"
              f"  up/flat/down {v['up']}/{v['flat']}/{v['down']}  ties {v['ties']} (mean_d {v['ties_mean_d'] if v['ties_mean_d'] is None else round(v['ties_mean_d'], 4)})"
              + (f"  axes {v['axes_mean']:+.2f}" if v["axes_mean"] is not None else ""))


if __name__ == "__main__":
    main()
