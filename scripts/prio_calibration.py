#!/usr/bin/env python3
"""prio_calibration — the PRIORITY slot's leaf-horizon calibration read
(ADR-0106 C1; m12-plan Build 3 evening 5).

The 09-11 pay-slot instrument (pay_calibration.py) moved to the first ply:
the same searched windows on heuristic games under three priority leaves
(-searchleaf next | h2 | end), each arm a final_read pair of seat runs on the
same pairs + seed base with the search observational (no -searchact). The
mainline is byte-identical across arms and the rate draw is a seed hash, so
the opts rows join by (seed, t, sw, seat) and the join rate is the identity
proof (reported; < 100% = investigate).

Per joined window the candidates valued in EVERY arm (a heuristic seat voids
options its own AI would not play — the same set on every arm) with >= 2 of
them; per horizon h:
  * SPREAD: max − min of the candidate means vs the roll sigma (pooled
    per-candidate SD over rolls) — the signal-to-noise curve: the share of
    windows whose spread clears 2 × SE(mean) is the "resolved" rate.
  * RANK AGREEMENT with the next leaf: mean per-window Spearman over the
    candidate means (windows with >= 3 candidates) and the top-pick agreement.
  * FLIPS: argmax_h ≠ argmax_next, and the END arm's verdict on them —
    d_end = v_end(argmax_h) − v_end(argmax_next), mean ± SE + the sign split
    (> 0: the deeper leaf's flips are right by the outcome).
  * CONVERSION of the acting rule at bars 0.05 / 0.10 (margin over the
    natural pick under the leaf): the end arm's mean of v_end(argmax_h) −
    v_end(natural) on those positives ± SE — what the acting rule buys by the
    outcome under each leaf. The end arm keyed on itself is the in-sample
    ceiling (winner's-cursed; a bound, not a read).
  * Per arm: windows, copies by kind, roll SD, ms per copy.
Usage:
  prio_calibration.py --arm next=dirS0,dirS1 --arm h2=... --arm end=... --out read.json
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import statistics as st
from collections import Counter
from pathlib import Path

import numpy as np

BARS = (0.05, 0.10)
GOOD_KINDS = {"leaf", "end", "draw"}


def _label_files(run: Path):
    return sorted(glob.glob(str(run / "workers" / "*" / "labels.jsonl"))) or sorted(
        glob.glob(str(run / "labels*.jsonl"))
    )


def load_arm(dirs: list[Path], counts: Counter) -> dict:
    """window key -> {opts: [{label, v, kind, snap, ms}], nat, leaf, seat, t}"""
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
                key = (int(r["seed"]), int(r["t"]), int(r["sw"]), int(r["seat"]))
                opts = []
                for o in r.get("opts") or []:
                    opts.append(
                        {
                            "label": o.get("label"),
                            "v": list(o.get("v") or []),
                            "kind": list(o.get("kind") or []),
                            "snap": o.get("snap"),
                            "ms": o.get("ms"),
                        }
                    )
                    for k in o.get("kind") or []:
                        counts[f"kind:{k}"] += 1
                if key in out:
                    counts["dup_key"] += 1
                out[key] = {
                    "opts": opts,
                    "nat": r.get("nat"),
                    "leaf": r.get("leaf"),
                    "seat": int(r["seat"]),
                    "t": int(r["t"]),
                }
    return out


def mean_value(o: dict) -> float | None:
    vs = [v for v, k in zip(o["v"], o["kind"]) if v is not None and k in GOOD_KINDS]
    return sum(vs) / len(vs) if vs else None


def roll_sd(o: dict) -> float | None:
    vs = [v for v, k in zip(o["v"], o["kind"]) if v is not None and k in GOOD_KINDS]
    return st.pstdev(vs) if len(vs) >= 2 else None


def n_good(o: dict) -> int:
    return sum(1 for v, k in zip(o["v"], o["kind"]) if v is not None and k in GOOD_KINDS)


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3:
        return None
    rx = np.argsort(np.argsort(x))
    ry = np.argsort(np.argsort(y))
    if np.std(rx) == 0 or np.std(ry) == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def mse(vals: list[float]) -> tuple[float | None, float | None]:
    if not vals:
        return None, None
    m = sum(vals) / len(vals)
    se = st.pstdev(vals) / math.sqrt(len(vals)) if len(vals) >= 2 else None
    return m, se


def fmt(m, se):
    if m is None:
        return "n/a"
    return f"{m:+.4f} ± {se:.4f}" if se is not None else f"{m:+.4f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", action="append", required=True, help="leaf=dir[,dir...]")
    ap.add_argument("--ref", default="next", help="the reference leaf for flips / rank agreement")
    ap.add_argument("--end", default="end", help="the outcome arm")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    arms: dict[str, dict] = {}
    counts: dict[str, Counter] = {}
    for spec in a.arm:
        leaf, _, dirs = spec.partition("=")
        counts[leaf] = Counter()
        arms[leaf] = load_arm([Path(d) for d in dirs.split(",") if d], counts[leaf])
    leaves = list(arms)
    ref, end = a.ref, a.end
    if ref not in arms:
        raise SystemExit(f"--ref {ref} is not an arm")

    # ---- join
    keys = set.intersection(*(set(w) for w in arms.values()))
    identical = 0
    joined = []
    for k in sorted(keys):
        labels = {leaf: [o["label"] for o in arms[leaf][k]["opts"]] for leaf in leaves}
        nats = {leaf: arms[leaf][k]["nat"] for leaf in leaves}
        same = len({json.dumps(v) for v in labels.values()}) == 1 and len(set(nats.values())) == 1
        if same:
            identical += 1
            joined.append(k)
    per_arm_windows = {leaf: len(w) for leaf, w in arms.items()}
    only = {leaf: len(set(arms[ref]) - set(arms[leaf])) for leaf in leaves if leaf != ref}
    print(
        f"prio_calibration: arms {leaves}; joined windows {len(keys)} (identical {identical} / mismatched "
        f"{len(keys) - identical}); windows per arm {per_arm_windows}; in {ref} only: {only}"
    )

    # ---- per-window candidate sets valued in every arm
    rows = []  # per joined window: {cands: [idx], means: {leaf: [..]}, nat_idx, seat, t}
    for k in joined:
        nopt = len(arms[ref][k]["opts"])
        cands = []
        for i in range(nopt):
            if all(mean_value(arms[leaf][k]["opts"][i]) is not None for leaf in leaves):
                cands.append(i)
        if len(cands) < 2:
            continue
        labels = [o["label"] for o in arms[ref][k]["opts"]]
        nat = arms[ref][k]["nat"]
        nat_idx = labels.index(nat) if nat in labels else -1
        means = {leaf: [mean_value(arms[leaf][k]["opts"][i]) for i in cands] for leaf in leaves}
        sds = {leaf: [roll_sd(arms[leaf][k]["opts"][i]) for i in cands] for leaf in leaves}
        ngs = {leaf: [n_good(arms[leaf][k]["opts"][i]) for i in cands] for leaf in leaves}
        rows.append(
            {
                "cands": cands,
                "means": means,
                "sds": sds,
                "ngood": ngs,
                "nat_pos": cands.index(nat_idx) if nat_idx in cands else -1,
                "seat": arms[ref][k]["seat"],
                "t": arms[ref][k]["t"],
            }
        )
    print(f"  windows with >= 2 candidates valued in every arm: {len(rows)}; candidates/window "
          f"{fmt(*mse([len(r['cands']) for r in rows]))}")

    out = {
        "arms": leaves,
        "joined": len(keys),
        "identical": identical,
        "windows_read": len(rows),
        "per_leaf": {},
    }

    for leaf in leaves:
        c = counts[leaf]
        spreads, sds, resolved = [], [], []
        rho, top_agree, flips, flip_d_end, flip_pos, flip_neg = [], [], 0, [], 0, 0
        conv = {b: [] for b in BARS}
        conv_n = {b: 0 for b in BARS}
        for r in rows:
            m = r["means"][leaf]
            spread = max(m) - min(m)
            spreads.append(spread)
            sd_here = [s for s in r["sds"][leaf] if s is not None]
            ng = [n for n in r["ngood"][leaf]]
            if sd_here:
                sd = sum(sd_here) / len(sd_here)
                sds.append(sd)
                se_mean = sd / math.sqrt(max(1, min(ng)))
                resolved.append(1.0 if spread > 2 * se_mean else 0.0)
            am = int(np.argmax(m))
            am_ref = int(np.argmax(r["means"][ref]))
            if leaf != ref:
                rr = spearman(m, r["means"][ref])
                if rr is not None:
                    rho.append(rr)
                top_agree.append(1.0 if am == am_ref else 0.0)
                if am != am_ref:
                    flips += 1
                    if end in arms:
                        me = r["means"][end]
                        d = me[am] - me[am_ref]
                        flip_d_end.append(d)
                        flip_pos += d > 0
                        flip_neg += d < 0
            if r["nat_pos"] >= 0 and end in arms:
                margin = m[am] - m[r["nat_pos"]]
                for b in BARS:
                    if margin >= b:
                        conv_n[b] += 1
                        me = r["means"][end]
                        conv[b].append(me[am] - me[r["nat_pos"]])
        kinds = {k[5:]: v for k, v in c.items() if k.startswith("kind:")}
        rec = {
            "windows_in_arm": per_arm_windows[leaf],
            "search_rows": c["search_rows"],
            "copies_by_kind": kinds,
            "spread_mean": mse(spreads),
            "spread_median": float(np.median(spreads)) if spreads else None,
            "roll_sd_mean": mse(sds),
            "resolved_rate": mse(resolved),
            "rho_vs_ref": mse(rho) if leaf != ref else None,
            "top_agree_vs_ref": mse(top_agree) if leaf != ref else None,
            "flips_vs_ref": flips if leaf != ref else None,
            "flip_d_end": mse(flip_d_end) if leaf != ref else None,
            "flip_sign": [flip_pos, flip_neg] if leaf != ref else None,
            "conversion": {str(b): {"n": conv_n[b], "d_end": mse(conv[b])} for b in BARS},
        }
        out["per_leaf"][leaf] = rec
        print(f"  {leaf:5s} windows {per_arm_windows[leaf]:5d} copies {dict(Counter(kinds).most_common(5))}")
        print(f"        spread {fmt(*rec['spread_mean'])} (median {rec['spread_median']:.4f}), roll sd "
              f"{fmt(*rec['roll_sd_mean'])}, resolved {fmt(*rec['resolved_rate'])}")
        if leaf != ref:
            print(f"        vs {ref}: rho {fmt(*rec['rho_vs_ref'])}, top agree {fmt(*rec['top_agree_vs_ref'])}, "
                  f"flips {flips}/{len(rows)}; d_end on flips {fmt(*rec['flip_d_end'])} "
                  f"(+{flip_pos} / −{flip_neg})")
        for b in BARS:
            print(f"        acting at bar {b}: positives {conv_n[b]}, d_end(argmax − natural) "
                  f"{fmt(*rec['conversion'][str(b)]['d_end'])}"
                  + ("  [in-sample ceiling]" if leaf == end else ""))

    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1))
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
