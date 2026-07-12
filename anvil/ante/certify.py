"""Ante certification runner (design §7 + m2-rl-plan D4).

Streams a trajectory store through the v0 ledger (anvil/ante/ledger.py) and
reports the two certification statistics:

  1. **Zero-mean**: every correction class sums to ~0 (per-node pooled AND
     game-clustered SEs — a bias here is a ledger bug, since corrections are
     zero-mean by construction).
  2. **Convergence**: corrected winrate reaches the truth no slower than raw
     (variance ratio + bootstrap CI; on an identical-deck mirror store the
     truth is 50% and the report adds |running mean − 0.5| curves).

The play/draw ("die") correction uses a leave-one-out empirical on-play
winrate per game — c_i computed from every OTHER game — so it stays exactly
zero-mean over the die roll while removing the play-advantage variance.

Works on any obs store (zero-mean + variance ratio are mirror-agnostic; the
50%-truth checks activate when every game is deck-vs-same-deck):

  uv run python -m anvil.ante.certify \\
      --store data/trajectories/<mirror-run> \\
      --ckpt data/training/d2-sa/last.pt \\
      --out data/runs/ante-cert.json
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np

from anvil.ante.ledger import MC_SAMPLES, ValueEvaluator, game_ledger
from anvil.store.trajectories import open_store
from anvil.training.dataset import _split_of

CLASSES = ("opener", "draw")


def _mean_se(x: np.ndarray) -> tuple[float, float]:
    if len(x) == 0:
        return float("nan"), float("nan")
    return float(x.mean()), float(x.std(ddof=1) / max(len(x), 2) ** 0.5)


def aggregate(ledgers: list[dict], bootstrap: int = 2000, seed: int = 0) -> dict:
    n = len(ledgers)
    raw = np.array([1.0 if L["winner"] == 0 else 0.0 for L in ledgers])
    luck = np.zeros(n)          # seat0 luck from opener+draw corrections
    per_class_node = {c: [] for c in CLASSES}
    per_class_game = {c: np.zeros(n) for c in CLASSES}  # signed seat0 sums
    for i, L in enumerate(ledgers):
        for r in L["nodes"]:
            sign = 1.0 if r["p"] == 0 else -1.0
            luck[i] += sign * r["corr"]
            per_class_node[r["cls"]].append(r["corr"])
            per_class_game[r["cls"]][i] += sign * r["corr"]

    # die: leave-one-out on-play winrate
    onp = np.array([L["on_play"] if L["on_play"] is not None else -1
                    for L in ledgers])
    have = onp >= 0
    onp_win = np.where(onp == np.array([L["winner"] for L in ledgers]), 1.0, 0.0)
    die = np.zeros(n)
    if have.sum() > 1:
        s, m = onp_win[have].sum(), int(have.sum())
        c_i = (s - onp_win) / (m - 1)          # leave-one-out c per game
        die = np.where(have, np.where(onp == 0, c_i - 0.5, 0.5 - c_i), 0.0)

    corrected = raw - luck - die
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(bootstrap, n))
    rv = raw[idx].var(axis=1, ddof=1)
    cv = corrected[idx].var(axis=1, ddof=1)
    ok = rv > 1e-6  # drop degenerate resamples (near-constant raw outcomes)
    vr = cv[ok] / rv[ok] if ok.any() else np.array([float("nan")])

    classes = {}
    for c in CLASSES:
        node = np.array(per_class_node[c])
        game = per_class_game[c]
        nm, nse = _mean_se(node)
        gm, gse = _mean_se(game)
        classes[c] = {
            "n_nodes": int(len(node)),
            "corr_mean_node": round(nm, 6), "corr_se_node": round(nse, 6),
            "t_node": round(nm / nse, 2) if nse > 0 else None,
            "seat0_sum_mean_game": round(gm, 6), "seat0_sum_se_game": round(gse, 6),
            "t_game": round(gm / gse, 2) if gse > 0 else None,
            "corr_abs_mean": round(float(np.abs(node).mean()), 6) if len(node) else None,
        }

    rm, rse = _mean_se(raw)
    cm, cse = _mean_se(corrected)
    lm, lse = _mean_se(luck)
    mirror = all(L["decks"][0] == L["decks"][1] for L in ledgers)
    out = {
        "games": n,
        "mirror": mirror,
        "raw_winrate": round(rm, 4), "raw_se": round(rse, 4),
        "corrected_winrate": round(cm, 4), "corrected_se": round(cse, 4),
        "ledger_mean": round(lm, 6), "ledger_se": round(lse, 6),
        "ledger_t": round(lm / lse, 2) if lse > 0 else None,
        "die_onplay_winrate": round(float(onp_win[have].mean()), 4) if have.any() else None,
        "die_n": int(have.sum()),
        "var_ratio": round(float(corrected.var(ddof=1) / raw.var(ddof=1)), 4),
        "var_ratio_ci90": [round(float(np.quantile(vr, q)), 4) for q in (0.05, 0.95)],
        "effective_sample_multiplier": round(float(raw.var(ddof=1) /
                                                   max(corrected.var(ddof=1), 1e-12)), 3),
        "classes": classes,
    }
    if mirror:
        # running |mean - 0.5| in game order (one ordering; bootstrap RMSE grid)
        grid = [g for g in (50, 100, 200, 400, 800, 1600, 3200, 6400, 12800) if g <= n]
        curves = {"n": grid, "raw_rmse": [], "corrected_rmse": []}
        for g in grid:
            sub = rng.integers(0, n, size=(500, g))
            curves["raw_rmse"].append(
                round(float(np.sqrt(((raw[sub].mean(axis=1) - 0.5) ** 2).mean())), 4))
            curves["corrected_rmse"].append(
                round(float(np.sqrt(((corrected[sub].mean(axis=1) - 0.5) ** 2).mean())), 4))
        out["convergence"] = curves
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True, help="store dir (comma-list ok)")
    ap.add_argument("--ckpt", default="data/training/d2-sa/last.pt")
    ap.add_argument("--split", default=None, choices=[None, "val", "valpair", "train"])
    ap.add_argument("--max-games", type=int, default=None)
    ap.add_argument("--mc", type=int, default=MC_SAMPLES)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--out", required=True, help="JSON report path")
    ap.add_argument("--ledger-out", default=None,
                    help="per-game ledger JSONL (default: <out>.ledger.jsonl)")
    a = ap.parse_args()

    ev = ValueEvaluator(a.ckpt, batch=a.batch)
    store = open_store(a.store)
    games = store.game_indices()
    if a.split:
        games = [g for g in games if _split_of(g) == a.split]
    if a.max_games:
        games = games[:a.max_games]
    print(f"[ante] ckpt step {ev.step}, {len(games)} games from {a.store}"
          f"{f' (split={a.split})' if a.split else ''}")

    ledger_path = Path(a.ledger_out or f"{a.out}.ledger.jsonl")
    ledgers: list[dict] = []
    skips: Counter = Counter()
    n_nodes = 0
    t0 = time.time()
    with open(ledger_path, "w") as lf:
        for j, g in enumerate(games):
            try:
                traj = store.game(g)
            except Exception as e:
                if "did not decompress" in str(e):
                    skips["quarantined_frame"] += 1
                    continue
                raise
            L = game_ledger(ev, traj, store.winner_seat(g), mc=a.mc)
            if L is None:
                skips["non_decisive"] += 1
                continue
            ledgers.append(L)
            skips.update(L["skips"])
            n_nodes += len(L["nodes"])
            lf.write(json.dumps(L) + "\n")
            if (j + 1) % 100 == 0 or j + 1 == len(games):
                dt = time.time() - t0
                print(f"[ante] {j + 1}/{len(games)} games, {n_nodes} nodes, "
                      f"{dt / (j + 1):.2f} s/game", flush=True)

    report = {
        "ckpt": ev.ckpt, "step": ev.step, "store": a.store, "split": a.split,
        "mc_samples": a.mc,
        "wall_s": round(time.time() - t0, 1),
        "skips": dict(skips),
        "emb_misses": dict(ev.emb_misses.most_common(20)),
        **aggregate(ledgers),
    }
    Path(a.out).write_text(json.dumps(report, indent=1) + "\n")

    print(f"\n[ante] {report['games']} decisive games, mirror={report['mirror']}")
    print(f"[ante] raw      {report['raw_winrate']:.4f} ± {report['raw_se']:.4f}")
    print(f"[ante] corrected {report['corrected_winrate']:.4f} ± {report['corrected_se']:.4f}")
    print(f"[ante] ledger mean {report['ledger_mean']:.6f} ± {report['ledger_se']:.6f} "
          f"(t={report['ledger_t']})")
    print(f"[ante] var ratio {report['var_ratio']} (90% CI {report['var_ratio_ci90']}), "
          f"effective-sample x{report['effective_sample_multiplier']}")
    for c, r in report["classes"].items():
        print(f"[ante]   {c}: n={r['n_nodes']}, node mean {r['corr_mean_node']} "
              f"± {r['corr_se_node']} (t={r['t_node']}), game-sum t={r['t_game']}, "
              f"|corr| mean {r['corr_abs_mean']}")
    print(f"[ante] skips: {dict(skips)}")
    print(f"[ante] report -> {a.out}\n[ante] per-game ledger -> {ledger_path}")


if __name__ == "__main__":
    main()
