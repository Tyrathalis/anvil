"""M6 D1 — the frozen-trunk ranking probe (the deciding experiment,
ADR-0038 / m6-plan D1).

Question: can *anything* learn to rank the 3,750 banked K=8 rollout
labels from frozen trunk features? The critic's held-out Spearman is
0.26-0.29 against a 0.94-0.97 repeat-measure ceiling (ADR-0036); this
probe separates "the outcome-label training was the bottleneck" (path A
— features carry live-vs-dead) from "the representation is blind"
(path B — encoder work).

Substrate: `critic-calibration-v1/dataset.jsonl` (every banked label:
store/g/fired-turn -> K=8 rollout winrate), the same deterministic 80/20
game split as `critic_calibration.py`, per-era fits (rollout truth is
policy-conditional).

Two frozen trunks, features captured at the identical positions via the
early-doom pairing convention (first obs-carrying decision of the fired
turn), windows built by the Ante ValueEvaluator (masked vs full-vis
auto-detected from the ckpt):

  policy-i019        data/training/d6-run11/iter-019/train/last.pt
  d4-critic-fullvis  data/training/d4-critic-fullvis/last.pt

The feature is the [STATE] read-out (out[:, 0], d=512) — the exact
vector the value head consumes; the [PLAN] latent rides along in the
dump for free but the pre-registered probes read [STATE].

Probe family (m6-plan D1.2): ridge + k-NN (sample-efficient) + a small
2-layer MLP, hyperparameters picked by game-grouped CV on the training
split only. Learning curves at 500/1K/2K/all training labels — a
"blind" verdict requires FLAT curves, not a low endpoint.

Pre-registered readings (comparison constants: critic floor 0.27,
repeat-measure ceiling 0.94-0.97): held-out Spearman >= ~0.7 and rising
=> path A; <= ~0.4 and flat => path B; between => price both.

Usage:
  uv run python scripts/frozen_probe.py features \
      --out data/runs/frozen-probe-v1
  uv run python scripts/frozen_probe.py probe \
      --out data/runs/frozen-probe-v1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

DATASET = "data/runs/critic-calibration-v1/dataset.jsonl"
CALIB_REPORT = "data/runs/critic-calibration-v1/report.json"
TRUNKS = {
    "policy-i019": "data/training/d6-run11/iter-019/train/last.pt",
    "d4-critic-fullvis": "data/training/d4-critic-fullvis/last.pt",
}
CURVE_SIZES = [500, 1000, 2000, None]  # None = all; override via --curve-sizes
RIDGE_ALPHAS = [0.1, 1.0, 10.0, 100.0, 1000.0]
KNN_KS = [5, 10, 25, 50]
CV_FOLDS = 5


def load_rows(path: str = DATASET) -> list[dict]:
    return [json.loads(line) for line in Path(path).open()]


def _held_out(store: str, g: int) -> bool:
    # identical to critic_calibration._held_out — the split must match
    h = hashlib.sha256(f"{store}:{g}".encode()).digest()
    return h[0] % 5 == 0


def _seat_of(store: str) -> int:
    if "-s0-" in store:
        return 0
    if "-s1-" in store:
        return 1
    raise ValueError(f"no seat marker in store name: {store}")


# ---------------------------------------------------------------- features


def features(args: argparse.Namespace) -> None:
    import torch

from anvil.torch.utils import get_torch_device

    from anvil.ante.ledger import ValueEvaluator
    from anvil.store.trajectories import TrajectoryStore
    from anvil.training.dataset import collate

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = load_rows(args.dataset)
    positions = sorted({(r["store"], r["g"], r["t"]) for r in rows})
    by_store: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for store, g, t in positions:
        by_store[store].append((g, t))
    print(f"[feat] {len(rows)} labels -> {len(positions)} unique positions "
          f"in {len(by_store)} stores")

    for trunk, ckpt in TRUNKS.items():
        t0 = time.time()
        ev = ValueEvaluator(ckpt)

        @torch.no_grad()
        def capture(examples: list[dict]) -> tuple[np.ndarray, ...]:
            ss, pp, vv = [], [], []
            for i in range(0, len(examples), ev.batch):
                chunk = collate(examples[i:i + ev.batch])
                chunk = {k: v.to(ev.device) for k, v in chunk.items()}
                with torch.autocast(ev.device, dtype=torch.bfloat16):
                    card_vecs = ev.net.cards(chunk["ent_emb"])
                    tokens, pad = ev.net.assemble(card_vecs, chunk)
                    out = ev.net.trunk(tokens, src_key_padding_mask=pad)
                    vlogit = ev.net.value_head(out[:, 0]).squeeze(-1)
                ss.append(out[:, 0].float().cpu().numpy())
                pp.append(out[:, 1].float().cpu().numpy())
                vv.append(torch.sigmoid(vlogit.float()).cpu().numpy())
            return (np.concatenate(ss), np.concatenate(pp),
                    np.concatenate(vv))

        keys, exs, missed = [], [], []
        for store, wants in sorted(by_store.items()):
            ts = TrajectoryStore(Path("data/trajectories") / store)
            seat = _seat_of(store)
            for g in sorted({g for g, _ in wants}):
                traj = ts.game(g)
                # first obs-carrying decision per turn — the exact
                # early_doom trace convention the labels were paired by
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
                    exs.append(ev.example(dec, traj.header, seat,
                                          traj.decisions[:i]))
        if missed:
            raise SystemExit(f"[feat] {len(missed)} positions missed the "
                             f"turn join, e.g. {missed[:3]} — convention "
                             "drift, refusing to write a partial dump")
        state, plan, val = capture(exs)
        np.savez_compressed(
            out_dir / f"features-{trunk}.npz",
            keys=np.array(keys), state=state, plan=plan, value=val)
        print(f"[feat] {trunk}: {len(keys)} positions, d={state.shape[1]}, "
              f"{time.time() - t0:.0f}s -> features-{trunk}.npz")

    # join sanity: the d4 trunk's value head IS the v_d4 column
    d4 = np.load(out_dir / "features-d4-critic-fullvis.npz")
    vmap = dict(zip(d4["keys"].tolist(), d4["value"].tolist()))
    diffs = [abs(vmap[f"{r['store']}:{r['g']}:{r['t']}"] - r["v_d4"])
             for r in rows]
    meta = {"dataset": args.dataset, "trunks": TRUNKS,
            "n_labels": len(rows), "n_positions": len(positions),
            "d4_value_join_check": {"mean_abs": round(float(np.mean(diffs)), 5),
                                    "max_abs": round(float(np.max(diffs)), 5)}}
    (out_dir / "features-meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"[feat] d4 value join check: mean|Δ|={meta['d4_value_join_check']['mean_abs']}"
          f" max|Δ|={meta['d4_value_join_check']['max_abs']} "
          "(rounding of the banked column is 4dp)")


# ---------------------------------------------------------------- probes


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra, rb = ra - ra.mean(), rb - rb.mean()
    den = np.sqrt((ra**2).sum() * (rb**2).sum())
    return float((ra * rb).sum() / den) if den > 0 else float("nan")


def _game_folds(games: list[str], folds: int) -> dict[str, int]:
    return {g: hashlib.sha256(f"cv:{g}".encode()).digest()[0] % folds
            for g in games}


def _standardize(xtr: np.ndarray, *rest: np.ndarray):
    mu, sd = xtr.mean(0), xtr.std(0) + 1e-8
    return tuple((x - mu) / sd for x in (xtr, *rest))


def _ridge_fit(x: np.ndarray, y: np.ndarray, alpha: float) -> np.ndarray:
    xb = np.hstack([x, np.ones((len(x), 1))])
    eye = np.eye(xb.shape[1])
    eye[-1, -1] = 0.0  # don't penalize the intercept
    return np.linalg.solve(xb.T @ xb + alpha * eye, xb.T @ y)


def _ridge_pred(x: np.ndarray, w: np.ndarray) -> np.ndarray:
    return np.hstack([x, np.ones((len(x), 1))]) @ w


def _knn_pred(xtr: np.ndarray, ytr: np.ndarray, xte: np.ndarray,
              k: int) -> np.ndarray:
    a = xtr / (np.linalg.norm(xtr, axis=1, keepdims=True) + 1e-8)
    b = xte / (np.linalg.norm(xte, axis=1, keepdims=True) + 1e-8)
    sim = b @ a.T
    idx = np.argpartition(-sim, min(k, sim.shape[1] - 1), axis=1)[:, :k]
    return ytr[idx].mean(1)


def _cv_pick(x: np.ndarray, y: np.ndarray, games: np.ndarray,
             fit_eval) -> tuple:
    """Pick a hyperparameter by game-grouped CV Spearman on the train split."""
    fold_of = _game_folds(sorted(set(games.tolist())), CV_FOLDS)
    fold = np.array([fold_of[g] for g in games])
    best, best_s = None, -2.0
    for hp, fe in fit_eval.items():
        ss = []
        for f in range(CV_FOLDS):
            m = fold == f
            if m.sum() < 20 or (~m).sum() < 50:
                continue
            ss.append(spearman(fe(x[~m], y[~m], x[m]), y[m]))
        s = float(np.mean(ss)) if ss else -2.0
        if s > best_s:
            best, best_s = hp, s
    return best, best_s


def _mlp_fit_pred(xtr: np.ndarray, ytr: np.ndarray, gtr: np.ndarray,
                  xte: np.ndarray, seed: int = 0) -> np.ndarray:
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    dev = get_torch_device()
    # game-grouped inner val split for early stopping
    val_m = np.array([hashlib.sha256(f"mlpval:{g}".encode()).digest()[0] % 7 == 0
                      for g in gtr])
    if val_m.sum() < 20:
        val_m = np.zeros(len(gtr), bool)
        val_m[:: max(len(gtr) // 20, 1)] = True
    xt = torch.tensor(xtr[~val_m], dtype=torch.float32, device=dev)
    yt = torch.tensor(ytr[~val_m], dtype=torch.float32, device=dev)
    xv = torch.tensor(xtr[val_m], dtype=torch.float32, device=dev)
    yv = ytr[val_m]
    net = nn.Sequential(nn.Linear(xtr.shape[1], 256), nn.ReLU(),
                        nn.Dropout(0.1), nn.Linear(256, 1)).to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-4)
    best_s, best_state, patience = -2.0, None, 0
    for epoch in range(300):
        net.train()
        perm = torch.randperm(len(xt), device=dev)
        for i in range(0, len(xt), 256):
            b = perm[i:i + 256]
            loss = ((torch.sigmoid(net(xt[b]).squeeze(-1)) - yt[b]) ** 2).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            pv = torch.sigmoid(net(xv).squeeze(-1)).cpu().numpy()
        s = spearman(pv, yv)
        if s > best_s:
            best_s, patience = s, 0
            best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
        else:
            patience += 1
            if patience >= 30:
                break
    if best_state is not None:
        net.load_state_dict(best_state)
    net.eval()
    with torch.no_grad():
        xe = torch.tensor(xte, dtype=torch.float32, device=dev)
        return torch.sigmoid(net(xe).squeeze(-1)).cpu().numpy()


def _curve_subset(games_tr: np.ndarray, size: int | None) -> np.ndarray:
    """Deterministic game-order subsample: add whole games until >= size rows."""
    if size is None:
        return np.ones(len(games_tr), bool)
    order = sorted(set(games_tr.tolist()),
                   key=lambda g: hashlib.sha256(f"lc:{g}".encode()).hexdigest())
    keep, n = set(), 0
    counts = {g: int((games_tr == g).sum()) for g in order}
    for g in order:
        if n >= size:
            break
        keep.add(g)
        n += counts[g]
    return np.isin(games_tr, list(keep))


def probe(args: argparse.Namespace) -> None:
    global CURVE_SIZES
    if args.curve_sizes:
        CURVE_SIZES = [int(s) if s != "all" else None
                       for s in args.curve_sizes.split(",")]
    out_dir = Path(args.out)
    rows = load_rows(args.dataset)
    feats = {t: np.load(out_dir / f"features-{t}.npz") for t in TRUNKS}
    idx_of = {t: {k: i for i, k in enumerate(f["keys"].tolist())}
              for t, f in feats.items()}

    report: dict = {"constants": {
        "critic_floor": "0.26-0.29 (ADR-0036 held-out raw/remapped Spearman)",
        "repeat_ceiling": "0.94-0.97 (repeat-measure ceiling)",
        "readings": "A: >=~0.7 rising | B: <=~0.4 flat | between: price both"}}
    calib = Path(CALIB_REPORT)
    if calib.exists():
        report["constants"]["repeat_noise"] = json.loads(
            calib.read_text())["repeat_noise"]

    for era in ("c1", "c2"):
        er = [r for r in rows if r["era"] == era]
        game_key = np.array([f"{r['store']}:{r['g']}" for r in er])
        ho = np.array([_held_out(r["store"], r["g"]) for r in er])
        y = np.array([r["wr"] for r in er])
        for trunk in TRUNKS:
            x_all = feats[trunk]["state"][
                [idx_of[trunk][f"{r['store']}:{r['g']}:{r['t']}"] for r in er]]
            res: dict = {"n_holdout": int(ho.sum())}
            # baseline: the banked critic value column, same split
            vcol = "v_era" if trunk == "policy-i019" else "v_d4"
            res[f"baseline_{vcol}_spearman"] = round(
                spearman(np.array([r[vcol] for r in er])[ho], y[ho]), 4)
            for size in CURVE_SIZES:
                sub = _curve_subset(game_key[~ho], size)
                xtr_r, ytr = x_all[~ho][sub], y[~ho][sub]
                gtr = game_key[~ho][sub]
                xtr, xte = _standardize(xtr_r, x_all[ho])
                tag = str(size) if size else "all"
                sz: dict = {"n_train": int(sub.sum())}

                alpha, cv_s = _cv_pick(xtr, ytr, gtr, {
                    a: (lambda xa, ya, xb, a=a:
                        _ridge_pred(xb, _ridge_fit(xa, ya, a)))
                    for a in RIDGE_ALPHAS})
                pred = _ridge_pred(xte, _ridge_fit(xtr, ytr, alpha))
                sz["ridge"] = {"spearman": round(spearman(pred, y[ho]), 4),
                               "alpha": alpha, "cv_spearman": round(cv_s, 4)}

                k, cv_s = _cv_pick(xtr, ytr, gtr, {
                    k: (lambda xa, ya, xb, k=k: _knn_pred(xa, ya, xb, k))
                    for k in KNN_KS})
                pred = _knn_pred(xtr, ytr, xte, k)
                sz["knn"] = {"spearman": round(spearman(pred, y[ho]), 4),
                             "k": k, "cv_spearman": round(cv_s, 4)}

                pred = _mlp_fit_pred(xtr, ytr, gtr, xte)
                sz["mlp"] = {"spearman": round(spearman(pred, y[ho]), 4)}

                res[tag] = sz
                print(f"[probe] {era}/{trunk} n={sz['n_train']}: "
                      f"ridge {sz['ridge']['spearman']} (a={alpha}) | "
                      f"knn {sz['knn']['spearman']} (k={k}) | "
                      f"mlp {sz['mlp']['spearman']}", flush=True)
            report[f"{era}/{trunk}"] = res

    (out_dir / "probe-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"[probe] -> {out_dir}/probe-report.json")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("features", features), ("probe", probe)):
        p = sub.add_parser(name)
        p.add_argument("--out", required=True)
        p.add_argument("--dataset", default=DATASET)
        p.add_argument("--curve-sizes", default=None,
                       help="probe only: comma list, 'all' = full train split "
                            "(default: 500,1000,2000,all)")
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
