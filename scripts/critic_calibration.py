"""Critic calibration vs banked K-rollout ground truth (M5 D3, ADR-0034
decision 3 + the post-ADR-0035 residual-decomposition rider).

Dataset: every drill label from the cycle-1/cycle-2 maps and anchor
sweeps — (store, game, fired turn) -> rollout winrate (model_wins/n,
K=8 argmax completions by that era's policy) — joined to the critic's
value at the same turn from the early_doom traces (first obs-carrying
decision of the turn, the same pairing convention the maps use for
v_before).

Two critics measured per era: the era's on-policy critic (iter-009 for
cycle 1, iter-019 for cycle 2) and the standing eval/Ante critic
(d4-critic-fullvis). Rollout truth is policy-conditional, so eras are
fit and reported separately; pooling is only justified if the per-era
maps agree.

Calibration: Platt (1-D logistic on the critic value) and isotonic
(PAV), fit on a deterministic 80% game split, measured held-out:
ECE(10), Brier, Spearman rank corr. The residual decomposition then
groups held-out isotonic residuals by turn bucket / ground-truth bin /
model deck / source, against the label-noise floor estimated from the
evalset baseline re-measures (same positions, same policy, argmax —
pure repeat noise).

Usage:
  uv run python scripts/critic_calibration.py --out data/runs/critic-calibration-v1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

ERAS = {
    "c1": {
        "labels": ["data/runs/drill-map-r9i9-k8"]
        + [f"data/runs/drill-sweep-lost-20260729/arm-{t}" for t in ("o0", "o2", "o4", "peak")],
        "traces": {
            "era": "data/runs/early-doom-run9-i009",
            "d4": "data/runs/early-doom-run9-d4crit",
        },
        "repeat": ("data/runs/drill-evalset-v2", "eval-20260801-150103.json"),
    },
    "c2": {
        "labels": ["data/runs/drill-map-r11i19-k8"]
        + [f"data/runs/drill-sweep-lost-20260804/arm-{t}" for t in ("o0", "o2", "o4", "peak")],
        "traces": {
            "era": "data/runs/early-doom-run11-i019",
            "d4": "data/runs/early-doom-run11-d4crit",
        },
        "repeat": ("data/runs/drill-evalset-v3", "eval-20260804-175808.json"),
    },
}

TURN_BUCKETS = [(1, 6), (7, 10), (11, 16), (17, 99)]


def _bin_of(wr: float) -> str:
    return (
        "lost" if wr <= 0.2 else "long_shot" if wr <= 0.45 else "coin" if wr <= 0.7 else "winnable"
    )


def _load_traces(path: str) -> dict[tuple, dict[int, float]]:
    out = {}
    for line in Path(path, "traces.jsonl").open():
        r = json.loads(line)
        out[(r["store"], r["g"])] = {t: v for t, v in r["vals"]}
    return out


def build_dataset(era: str, cfg: dict) -> list[dict]:
    tr = {k: _load_traces(p) for k, p in cfg["traces"].items()}
    rows, miss = [], 0
    for src in cfg["labels"]:
        for line in Path(src, "drills.jsonl").open():
            r = json.loads(line)
            if r["n"] <= 0:
                continue
            key = (r["store"], r["g"])
            t = r["fired_t"]
            vals = {k: tr[k].get(key, {}).get(t) for k in tr}
            if any(v is None for v in vals.values()):
                miss += 1
                continue
            rows.append(
                {
                    "era": era,
                    "src": Path(src).name,
                    "store": r["store"],
                    "g": r["g"],
                    "t": t,
                    "wr": r["model_wins"] / r["n"],
                    "n": r["n"],
                    "v_era": vals["era"],
                    "v_d4": vals["d4"],
                    "deck": r["deck"],
                }
            )
    print(f"[data] {era}: {len(rows)} labels ({miss} trace-join misses)")
    return rows


def _held_out(row: dict) -> bool:
    h = hashlib.sha256(f"{row['store']}:{row['g']}".encode()).digest()
    return h[0] % 5 == 0  # deterministic ~20% by GAME


def platt_fit(v: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """1-D logistic y ~ sigmoid(a*logit(v)+b), Newton iterations."""
    x = np.log(np.clip(v, 1e-4, 1 - 1e-4) / (1 - np.clip(v, 1e-4, 1 - 1e-4)))
    a, b = 1.0, 0.0
    for _ in range(50):
        z = np.clip(a * x + b, -30, 30)
        p = 1 / (1 + np.exp(-z))
        w = np.clip(p * (1 - p), 1e-8, None)
        ga, gb = ((p - y) * x).sum(), (p - y).sum()
        haa, hab, hbb = (w * x * x).sum(), (w * x).sum(), w.sum()
        det = haa * hbb - hab * hab
        if abs(det) < 1e-12:
            break
        da, db = (hbb * ga - hab * gb) / det, (haa * gb - hab * ga) / det
        a, b = a - da, b - db
        if abs(da) + abs(db) < 1e-10:
            break
    return a, b


def platt_apply(v, a, b):
    x = np.log(np.clip(v, 1e-4, 1 - 1e-4) / (1 - np.clip(v, 1e-4, 1 - 1e-4)))
    return 1 / (1 + np.exp(-np.clip(a * x + b, -30, 30)))


def pav_fit(v: np.ndarray, y: np.ndarray):
    """Isotonic regression (pool adjacent violators) -> step function."""
    order = np.argsort(v, kind="mergesort")
    xs, ys = v[order], y[order].astype(float)
    w = np.ones(len(ys))
    vals, wts, lo = [], [], []
    for i in range(len(ys)):
        vals.append(ys[i])
        wts.append(w[i])
        lo.append(xs[i])
        while len(vals) > 1 and vals[-2] >= vals[-1]:
            wv = wts[-1] + wts[-2]
            vals[-2] = (vals[-1] * wts[-1] + vals[-2] * wts[-2]) / wv
            wts[-2] = wv
            vals.pop()
            wts.pop()
            lo.pop()
    return np.array(lo), np.array(vals)


def pav_apply(v: np.ndarray, lo: np.ndarray, vals: np.ndarray) -> np.ndarray:
    idx = np.searchsorted(lo, v, side="right") - 1
    return vals[np.clip(idx, 0, len(vals) - 1)]


def ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    b = np.clip((p * bins).astype(int), 0, bins - 1)
    e = 0.0
    for i in range(bins):
        m = b == i
        if m.any():
            e += m.mean() * abs(p[m].mean() - y[m].mean())
    return e


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra, rb = ra - ra.mean(), rb - rb.mean()
    return float((ra * rb).sum() / math.sqrt((ra**2).sum() * (rb**2).sum()))


def repeat_noise(evalset_dir: str, eval_file: str) -> dict:
    """Same position, same policy, argmax, measured twice (map labels vs
    the evalset baseline re-measure): the achievable-agreement floor."""
    rows = json.loads(Path(evalset_dir, eval_file).read_text())["rows"]
    d = [
        r["model_wins"] / r["n"] - r["base_wins"] / r["base_n"]
        for r in rows
        if r["n"] > 0 and r["base_n"] > 0
    ]
    d = np.array(d)
    return {
        "n": len(d),
        "mean": round(float(d.mean()), 4),
        "sd_pair": round(float(d.std()), 4),
        "sd_single": round(float(d.std() / math.sqrt(2)), 4),
    }


def evaluate(era: str, rows: list[dict], critic_key: str, out: dict) -> None:
    tr = [r for r in rows if not _held_out(r)]
    ho = [r for r in rows if _held_out(r)]
    v_tr = np.array([r[critic_key] for r in tr])
    y_tr = np.array([r["wr"] for r in tr])
    v_ho = np.array([r[critic_key] for r in ho])
    y_ho = np.array([r["wr"] for r in ho])

    a, b = platt_fit(v_tr, y_tr)
    lo, vals = pav_fit(v_tr, y_tr)
    preds = {"raw": v_ho, "platt": platt_apply(v_ho, a, b), "isotonic": pav_apply(v_ho, lo, vals)}
    res = {}
    for name, p in preds.items():
        res[name] = {
            "ece": round(ece(p, y_ho), 4),
            "brier": round(float(((p - y_ho) ** 2).mean()), 4),
            "spearman": round(spearman(p, y_ho), 4),
        }
    res["n_train"], res["n_holdout"] = len(tr), len(ho)
    res["platt_ab"] = [round(a, 4), round(b, 4)]
    res["mean_v_raw"] = round(float(v_ho.mean()), 4)
    res["mean_wr"] = round(float(y_ho.mean()), 4)

    # ---- residual decomposition on held-out isotonic ----
    p_iso = preds["isotonic"]
    resid = p_iso - y_ho
    groups: dict[str, dict] = defaultdict(lambda: {"n": 0, "sum": 0.0, "abs": 0.0})
    deck_g: dict[str, dict] = defaultdict(lambda: {"n": 0, "sum": 0.0})
    for r, e in zip(ho, resid):
        tb = next(f"t{lo_}-{hi}" for lo_, hi in TURN_BUCKETS if lo_ <= r["t"] <= hi)
        for gk in (
            f"turn:{tb}",
            f"bin:{_bin_of(r['wr'])}",
            f"src:{'map' if 'map' in r['src'] else 'sweep'}",
        ):
            g = groups[gk]
            g["n"] += 1
            g["sum"] += e
            g["abs"] += abs(e)
        dg = deck_g[r["deck"]]
        dg["n"] += 1
        dg["sum"] += e
    res["residual_groups"] = {
        k: {
            "n": g["n"],
            "mean": round(g["sum"] / g["n"], 4),
            "mean_abs": round(g["abs"] / g["n"], 4),
        }
        for k, g in sorted(groups.items())
    }
    worst = sorted(
        ((d, g["sum"] / g["n"], g["n"]) for d, g in deck_g.items() if g["n"] >= 8),
        key=lambda x: -abs(x[1]),
    )[:8]
    res["worst_decks"] = [{"deck": d, "mean_resid": round(m, 4), "n": n} for d, m, n in worst]
    out[f"{era}/{critic_key}"] = res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    report: dict = {"repeat_noise": {}}
    all_rows = []
    for era, cfg in ERAS.items():
        rows = build_dataset(era, cfg)
        all_rows += rows
        report["repeat_noise"][era] = repeat_noise(*cfg["repeat"])
        for ck in ("v_era", "v_d4"):
            evaluate(era, rows, ck, report)

    with (out_dir / "dataset.jsonl").open("w") as f:
        for r in all_rows:
            f.write(json.dumps(r) + "\n")
    (out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: {
                    m: v
                    for m, v in r.items()
                    if m in ("raw", "platt", "isotonic", "n_holdout", "mean_v_raw", "mean_wr")
                }
                if isinstance(r, dict) and "raw" in r
                else r
                for k, r in report.items()
            },
            indent=2,
        )
    )
    print(f"[calib] -> {out_dir}/report.json + dataset.jsonl ({len(all_rows)} labels)")


if __name__ == "__main__":
    main()
