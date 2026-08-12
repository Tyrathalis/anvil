"""M6 D2-B lever B-1 — the derived-state feature probe (ADR-0042).

Question: does state-level arithmetic (race/lethality, clock,
castability-vs-mana, material/card-advantage, commander-tax — computed
transform-side from the logged full-state obs, anvil/encoder/derived.py)
carry the live-vs-dead ranking signal the frozen `[STATE]` vector provably
lacks?

Gate (ADR-0041/0042, standing): beat the 0.455 ridge / ~0.46 plateau on the
frozen `frozen-probe-ext2-c2` benchmark, identical split. Everything is
inherited from scripts/frozen_probe.py so numbers are comparable:
same dataset rows, same deterministic 80/20 game split, same game-grouped
CV alpha pick, same ridge; the `[STATE]` vectors are the banked
features-policy-i019.npz dump (no GPU pass here — B-1 is pure Python).

Per-family attribution (ADR-0042 decision 2 — the probe layer IS the
attribution discipline): for each family F we fit
  state+F        (marginal value on top of [STATE])
  F alone        (how much the family carries by itself)
  state+all-F    (leave-one-out: what dies without it)
plus state (baseline reproduction), feats (all families, no trunk), and
state+all (the bundle the graduated run would feed).

Usage:
  uv run python scripts/feature_probe.py features \
      --out data/runs/frozen-probe-ext2-c2
  uv run python scripts/feature_probe.py probe \
      --out data/runs/frozen-probe-ext2-c2
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frozen_probe as fp  # noqa: E402  (split/CV/ridge of record)

from anvil.encoder.derived import (  # noqa: E402
    DERIVED_VERSION,
    FAMILY_OF,
    FEATURE_NAMES,
    collect_names,
    derived_features,
    load_statics,
)

DATASET = "data/runs/frozen-probe-ext2-c2/dataset.jsonl"
TRUNK = "policy-i019"  # the gate trunk (out-ranks d4 both eras, ADR-0039)
CURVE_SIZES = [1000, 2000, None]  # curve read for state / state+all only


# ---------------------------------------------------------------- features


def features(args: argparse.Namespace) -> None:
    from anvil.store.trajectories import TrajectoryStore

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = fp.load_rows(args.dataset)
    positions = sorted({(r["store"], r["g"], r["t"]) for r in rows})
    by_store: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for store, g, t in positions:
        by_store[store].append((g, t))
    print(
        f"[dfeat] {len(rows)} labels -> {len(positions)} unique positions in {len(by_store)} stores"
    )

    t0 = time.time()
    keys, pending, missed = [], [], []
    wanted_names: set[str] = set()
    for store, wants in sorted(by_store.items()):
        ts = TrajectoryStore(Path("data/trajectories") / store)
        seat = fp._seat_of(store)
        for g in sorted({g for g, _ in wants}):
            traj = ts.game(g)
            # first obs-carrying decision per turn — the exact early_doom
            # trace convention the labels were paired by (== frozen_probe)
            first_of_turn: dict[int, int] = {}
            seen_turn = -1
            for i, dec in enumerate(traj.decisions):
                obs = dec.get("obs")
                if obs is None:
                    continue
                turn = obs["glob"].get("turn", 0)
                if turn < 1 or turn == seen_turn:
                    continue
                seen_turn = turn
                first_of_turn[turn] = i
            for g2, t in wants:
                if g2 != g:
                    continue
                i = first_of_turn.get(t)
                if i is None:
                    missed.append((store, g, t))
                    continue
                dec = traj.decisions[i]
                keys.append(f"{store}:{g}:{t}")
                pending.append((dec, traj.header, seat))
                wanted_names |= collect_names(dec, traj.header, seat)
    if missed:
        raise SystemExit(
            f"[dfeat] {len(missed)} positions missed the turn "
            f"join, e.g. {missed[:3]} — convention drift, "
            "refusing to write a partial dump"
        )

    statics = load_statics(wanted_names)
    misses = sorted(wanted_names - statics.keys())
    feats = np.stack(
        [derived_features(dec, header, seat, statics) for dec, header, seat in pending]
    )
    np.savez_compressed(
        out_dir / "derived-features.npz",
        keys=np.array(keys),
        feats=feats,
        feature_names=np.array(FEATURE_NAMES),
        family=np.array([FAMILY_OF[n] for n in FEATURE_NAMES]),
    )
    meta = {
        "dataset": args.dataset,
        "derived_version": DERIVED_VERSION,
        "n_positions": len(keys),
        "n_features": len(FEATURE_NAMES),
        "statics": {
            "wanted": len(wanted_names),
            "resolved": len(statics),
            "missed": len(misses),
            "missed_names": misses[:40],
        },
        "per_feature_std": {n: round(float(s), 3) for n, s in zip(FEATURE_NAMES, feats.std(0))},
    }
    (out_dir / "derived-features-meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(
        f"[dfeat] {len(keys)} positions x {len(FEATURE_NAMES)} features "
        f"in {time.time() - t0:.0f}s; statics {len(statics)}/"
        f"{len(wanted_names)} resolved ({len(misses)} missed, e.g. "
        f"{misses[:5]}) -> derived-features.npz"
    )
    dead = [n for n, s in zip(FEATURE_NAMES, feats.std(0)) if s == 0]
    if dead:
        print(f"[dfeat] WARNING constant features (std=0): {dead}")


# ---------------------------------------------------------------- probe


def _fit_eval(
    xtr_r: np.ndarray, ytr: np.ndarray, gtr: np.ndarray, xte_r: np.ndarray, yte: np.ndarray
) -> dict:
    xtr, xte = fp._standardize(xtr_r, xte_r)
    alpha, cv_s = fp._cv_pick(
        xtr,
        ytr,
        gtr,
        {
            a: (lambda xa, ya, xb, a=a: fp._ridge_pred(xb, fp._ridge_fit(xa, ya, a)))
            for a in fp.RIDGE_ALPHAS
        },
    )
    pred = fp._ridge_pred(xte, fp._ridge_fit(xtr, ytr, alpha))
    return {
        "spearman": round(fp.spearman(pred, yte), 4),
        "alpha": alpha,
        "cv_spearman": round(cv_s, 4),
    }


def probe(args: argparse.Namespace) -> None:
    out_dir = Path(args.out)
    rows = fp.load_rows(args.dataset)
    state_npz = np.load(out_dir / f"features-{TRUNK}.npz")
    # --features-npz: any keys/feats/feature_names/family bundle probes
    # through the identical machinery (otag probe etc.); default = B-1
    drv = np.load(args.features_npz or (out_dir / "derived-features.npz"))
    state_idx = {k: i for i, k in enumerate(state_npz["keys"].tolist())}
    drv_idx = {k: i for i, k in enumerate(drv["keys"].tolist())}
    fam = drv["family"]
    families = sorted(set(fam.tolist()))
    fam_cols = {f: np.where(fam == f)[0] for f in families}

    report: dict = {
        "constants": {
            "gate": "beat the 0.455 ridge / ~0.46 plateau on c2 (ADR-0041 "
            "standing gate) — identical split, banked [STATE] dump",
            "trunk": TRUNK,
            "features_npz": str(args.features_npz or "derived-features.npz"),
            "families": {f: int(len(c)) for f, c in fam_cols.items()},
        }
    }

    for era in ("c1", "c2"):
        er = [r for r in rows if r["era"] == era]
        if not er:
            continue
        keys = [f"{r['store']}:{r['g']}:{r['t']}" for r in er]
        game_key = np.array([f"{r['store']}:{r['g']}" for r in er])
        ho = np.array([fp._held_out(r["store"], r["g"]) for r in er])
        y = np.array([r["wr"] for r in er])
        x_state = state_npz["state"][[state_idx[k] for k in keys]]
        x_drv = drv["feats"][[drv_idx[k] for k in keys]].astype(np.float64)

        cfgs: dict[str, np.ndarray] = {
            "state": x_state,
            "feats": x_drv,
            "state+all": np.hstack([x_state, x_drv]),
        }
        for f in families:
            cols = fam_cols[f]
            rest = np.setdiff1d(np.arange(x_drv.shape[1]), cols)
            cfgs[f"state+{f}"] = np.hstack([x_state, x_drv[:, cols]])
            cfgs[f"{f}-alone"] = x_drv[:, cols]
            cfgs[f"state+all-{f}"] = np.hstack([x_state, x_drv[:, rest]])

        res: dict = {"n_holdout": int(ho.sum()), "n_train": int((~ho).sum())}
        for name, x in cfgs.items():
            r = _fit_eval(x[~ho], y[~ho], game_key[~ho], x[ho], y[ho])
            res[name] = r
            print(
                f"[probe] {era} {name:>14}: {r['spearman']:.4f} "
                f"(a={r['alpha']}, cv={r['cv_spearman']:.4f})",
                flush=True,
            )
        base = res["state"]["spearman"]
        res["delta_vs_state"] = {
            n: round(res[n]["spearman"] - base, 4) for n in cfgs if n != "state"
        }

        # curve read on the bundle: a real representation gain should hold
        # (or rise) with n, not be a small-n artifact
        for cfg in ("state", "state+all"):
            curve = {}
            for size in CURVE_SIZES:
                sub = fp._curve_subset(game_key[~ho], size)
                r = _fit_eval(
                    cfgs[cfg][~ho][sub], y[~ho][sub], game_key[~ho][sub], cfgs[cfg][ho], y[ho]
                )
                curve[str(size) if size else "all"] = r["spearman"]
            res[f"curve_{cfg}"] = curve
            print(f"[probe] {era} curve {cfg}: {curve}", flush=True)
        report[era] = res

    name = args.report or "feature-probe-report.json"
    (out_dir / name).write_text(json.dumps(report, indent=2) + "\n")
    print(f"[probe] -> {out_dir}/{name}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("features", features), ("probe", probe)):
        p = sub.add_parser(name)
        p.add_argument("--out", required=True)
        p.add_argument("--dataset", default=DATASET)
        if name == "probe":
            p.add_argument(
                "--features-npz",
                default=None,
                help="probe an alternative feature bundle (keys/feats/feature_names/family npz)",
            )
            p.add_argument("--report", default=None, help="report filename in --out")
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
