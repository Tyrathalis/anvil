#!/usr/bin/env python3
"""The ALLOCATION HEAD's first fit (ADR-0109 item 2; m12-plan forks D / L) — the
frozen-trunk read on the search's own rows. Question: from the state at a
priority window alone, how well can a head predict that the search will act
there (its margin >= the acting bar), and how much box time would allocating
the search by that head save at a given recall (the games multiplier)?

build: join every search row (a run's workers/*/labels.jsonl, ev = search) to
  its priority dec in the run's ingested store (game by seed; within a game
  (t, ph, seat) + the row's 60-char option labels as a sub-multiset of the
  dec's option strings, consumed in stream order — 100% on the 09-15 bench
  cell), featurize with the checkpoint's serve featurizer, run the frozen
  trunk, dump [STATE] + scalars + labels -> <out>/features.npz.
probe: game-grouped K folds (seed hash); a logistic head on standardized
  [STATE] (+ scalars) vs scalars alone; labels margin >= 0.10 (the acting
  bar), >= 0.02 (the deep band's lo); AUC per fold; the allocation curve at a
  uniform floor f: box-time share searched (forward calls) vs acts captured;
  the games multiplier at 80 / 90 / 95% recall.
Usage:
  uv run python scripts/alloc_fit.py build --runs <dir,dir,...> --out data/runs/alloc-fit-1
  uv run python scripts/alloc_fit.py probe --out data/runs/alloc-fit-1 [--folds 5 --floor 0.1]
"""
from __future__ import annotations

import argparse
import collections
import glob
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
CKPT = "data/training/m12-build3-e3/last.pt"
PH = {"MAIN1": 0, "MAIN2": 1}


def _norm(s) -> str:
    return (s or "")[:60]


def join_run(run: Path, store: Path):
    """(row, dec, traj) triples for every search row that joins; stats."""
    from anvil.store.trajectories import TrajectoryStore

    st = TrajectoryStore(store)
    rows = [json.loads(l) for f in glob.glob(str(run / "workers/*/labels.jsonl"))
            for l in open(f) if '"ev":"search"' in l]
    by_seed = collections.defaultdict(list)
    for r in rows:
        by_seed[r["seed"]].append(r)
    for v in by_seed.values():
        v.sort(key=lambda r: r["sw"])
    seed2g = {st.game(g).header["seed"]: g for g in st.game_indices()}
    stats = collections.Counter(rows=len(rows))
    for seed, rs in by_seed.items():
        if seed not in seed2g:
            stats["game_missing"] += len(rs)
            continue
        traj = st.game(seed2g[seed])
        decs = traj.decisions
        prio = [(i, d) for i, d in enumerate(decs)
                if d["m"] == "chooseSpellAbilityToPlay" and d.get("ph") in PH]
        di = 0
        for r in rs:
            want = collections.Counter(_norm(o["label"]) for o in r["opts"] if o["label"] != "pass")
            found = None
            j = di
            while j < len(prio):
                _, d = prio[j]
                if d["t"] > r["t"]:
                    break
                if d["t"] == r["t"] and d["ph"] == r["ph"] and d["p"] == r["seat"]:
                    have = collections.Counter(_norm(str(o.get("sa") or "")) for o in d["opts"])
                    if not (want - have) and len(d["opts"]) >= r["n_opts"]:
                        found = j
                        break
                j += 1
            if found is None:
                stats["unjoined"] += 1
                continue
            di = found + 1
            stats["joined"] += 1
            yield r, prio[found][0], traj
    print(f"[join] {run.name}: {dict(stats)}", flush=True)


def build(a) -> None:
    import torch
    from anvil.bridge.featurize import Featurizer, store_wire_hist
    from anvil.training.dataset import collate, default_methods
    from anvil.training.surface_fit import load_net

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    net, ck = load_net(a.ckpt, dev)
    net.eval()
    cfg = ck["config"]
    # the serve path's featurizer (anvil.bridge.server: ability_table only under the
    # M10 "hand" sched basis, never on the M12 recipe)
    feat = Featurizer(cfg["embed"], default_methods(), abilities=cfg.get("abilities"))
    states, scal, meta = [], [], []
    stats = collections.Counter()
    t0 = time.time()

    @torch.no_grad()
    def trunk(exs):
        bt = collate(exs)
        bt = {k: (v.to(dev) if torch.is_tensor(v) else v) for k, v in bt.items()}
        with torch.autocast(dev, dtype=torch.bfloat16, enabled=dev == "cuda"):
            card_vecs = net.cards(bt["ent_emb"])
            tokens, pad = net.assemble(card_vecs, bt)
            o = net.trunk(tokens, src_key_padding_mask=pad)
            v = torch.sigmoid(net.value_head(o[:, 0]).squeeze(-1).float())
        return o[:, 0].float().cpu().numpy(), v.cpu().numpy()

    pending, pmeta = [], []

    def flush():
        if not pending:
            return
        s, v = trunk(pending)
        states.append(s)
        for m, vv in zip(pmeta, v):
            m["win"] = float(vv)
            meta.append(m)
        pending.clear()
        pmeta.clear()

    for run in a.runs.split(","):
        run = Path(run)
        store = REPO / "data/trajectories" / run.name
        for r, di, traj in join_run(run, store):
            decs = traj.decisions
            dec = decs[di]
            wire = dict(dec)
            if "hist" not in dec:
                wire["hist"] = store_wire_hist(decs[:di], dec.get("_pos", di))
            try:
                ex, _aux = feat.example(wire, traj.header, "priority")
            except Exception as e:  # noqa: BLE001
                stats[f"featurize_{type(e).__name__}"] += 1
                continue
            ex = {k: v for k, v in ex.items() if torch.is_tensor(v)}
            calls = sum(sum(c for c in o.get("calls", []) if isinstance(c, (int, float))) for o in r["opts"])
            m = {"src": run.name, "seed": r["seed"], "sw": r["sw"], "t": r["t"], "ph": r["ph"], "seat": r["seat"],
                 "n_opts": r["n_opts"], "margin": float(r.get("margin") or 0.0), "by": r.get("by"),
                 "applied": r.get("applied"), "calls": int(calls), "ms": int(r.get("ms") or 0),
                 "deep": json.dumps(r["deep"]) if "deep" in r else None}
            pending.append(ex)
            pmeta.append(m)
            if len(pending) >= a.batch:
                flush()
                if len(meta) % 2000 < a.batch:
                    print(f"[build] {len(meta)} windows ({time.time() - t0:.0f}s)", flush=True)
    flush()
    S = np.concatenate(states) if states else np.zeros((0, 0), np.float32)
    np.savez_compressed(out / "features.npz", state=S)
    with open(out / "meta.jsonl", "w") as fh:
        for m in meta:
            fh.write(json.dumps(m) + "\n")
    print(f"[build] {len(meta)} windows, state dim {S.shape[1] if S.size else 0}, stats {dict(stats)} "
          f"-> {out} ({time.time() - t0:.0f}s)", flush=True)


# ---------------------------------------------------------------- probe

def _auc(score: np.ndarray, y: np.ndarray) -> float:
    pos, neg = score[y == 1], score[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order), float)
    ranks[order] = np.arange(1, len(order) + 1)
    # average ranks for ties
    allv = np.concatenate([pos, neg])
    _, inv, cnt = np.unique(allv, return_inverse=True, return_counts=True)
    sums = np.zeros(len(cnt))
    np.add.at(sums, inv, ranks)
    ranks = sums[inv] / cnt[inv]
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def _logistic(xtr, ytr, xte, l2: float, seed: int):
    import torch
    torch.manual_seed(seed)
    X = torch.tensor(xtr, dtype=torch.float32)
    Y = torch.tensor(ytr, dtype=torch.float32)
    w = torch.zeros(X.shape[1], requires_grad=True)
    b = torch.zeros(1, requires_grad=True)
    pos_w = float((len(Y) - Y.sum()) / max(1.0, Y.sum()))
    opt = torch.optim.LBFGS([w, b], lr=0.5, max_iter=200, line_search_fn="strong_wolfe")

    def closure():
        opt.zero_grad()
        logit = X @ w + b
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logit, Y, pos_weight=torch.tensor(pos_w))
        loss = loss + l2 * (w * w).sum()
        loss.backward()
        return loss

    opt.step(closure)
    with torch.no_grad():
        return (torch.tensor(xte, dtype=torch.float32) @ w + b).numpy()


def _fold(seed: int, folds: int) -> int:
    return int(hashlib.sha1(str(seed).encode()).hexdigest()[:8], 16) % folds


def _alloc_curve(score, y, cost, floor: float, seed: int = 0):
    """Search the top-q by score plus a seeded floor draw; return, per q, the
    cost share searched and the share of positives (acts) captured."""
    rng = np.random.default_rng(seed)
    fl = rng.random(len(score)) < floor
    order = np.argsort(-score)
    tot_cost, tot_pos = cost.sum(), max(1, y.sum())
    out = []
    for q in np.linspace(0.0, 1.0, 41):
        k = int(round(q * len(score)))
        sel = np.zeros(len(score), bool)
        sel[order[:k]] = True
        sel |= fl
        out.append((float(q), float(cost[sel].sum() / tot_cost), float(y[sel].sum() / tot_pos),
                    float(sel.mean())))
    return out


def probe(a) -> None:
    out = Path(a.out)
    S = np.load(out / "features.npz")["state"]
    meta = [json.loads(l) for l in open(out / "meta.jsonl")]
    n = len(meta)
    assert S.shape[0] == n, (S.shape, n)
    margin = np.array([m["margin"] for m in meta])
    n_opts = np.array([m["n_opts"] for m in meta], float)
    calls = np.array([max(1, m["calls"]) for m in meta], float)
    scal = np.stack([n_opts, np.log1p(n_opts), np.array([m["t"] for m in meta], float),
                     np.array([PH[m["ph"]] for m in meta], float),
                     np.array([m["seat"] for m in meta], float),
                     np.array([m["win"] for m in meta], float)], 1)
    folds = np.array([_fold(m["seed"], a.folds) for m in meta])
    single = n_opts <= 0
    print(f"[probe] {n} windows from {len(set(m['src'] for m in meta))} runs; singles (n_opts 0) "
          f"{single.mean():.1%}; acts (by=search) {np.mean([m['by'] == 'search' for m in meta]):.1%}; "
          f"margin >= 0.10: {np.mean(margin >= 0.10):.1%}, >= 0.05: {np.mean(margin >= 0.05):.1%}, "
          f">= 0.02: {np.mean(margin >= 0.02):.1%}")
    res = {"n": n, "folds": a.folds, "floor": a.floor, "bars": {}}
    for bar in (0.10, 0.05, 0.02):
        y = (margin >= bar).astype(int)
        feats = {"scalars": scal, "state": S, "state+scalars": np.concatenate([S, scal], 1)}
        r = {"pos_rate": float(y.mean())}
        for name, X in feats.items():
            aucs, oof = [], np.zeros(n)
            for f in range(a.folds):
                tr, te = folds != f, folds == f
                mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-6
                sc = _logistic((X[tr] - mu) / sd, y[tr], (X[te] - mu) / sd, a.l2, f)
                oof[te] = sc
                aucs.append(_auc(sc, y[te]))
            r[name] = {"auc_mean": float(np.nanmean(aucs)), "auc_sd": float(np.nanstd(aucs)),
                       "auc_folds": [round(x, 4) for x in aucs]}
            if name == "state+scalars":
                curve = _alloc_curve(oof, y, calls, a.floor)
                r["alloc_curve"] = curve
                mult = {}
                for rec in (0.8, 0.9, 0.95):
                    hit = next((c for c in curve if c[2] >= rec), None)
                    mult[str(rec)] = None if hit is None else {"cost_share": hit[1], "windows_share": hit[3],
                                                                "games_mult": 1.0 / max(1e-6, hit[1])}
                r["games_multiplier"] = mult
            print(f"[probe] bar {bar}: {name:14s} AUC {r[name]['auc_mean']:.3f} ± {r[name]['auc_sd']:.3f}", flush=True)
        if "games_multiplier" in r:
            for k, v in r["games_multiplier"].items():
                if v:
                    print(f"[probe] bar {bar}: capture {k} of acts at cost share {v['cost_share']:.2f} "
                          f"({v['windows_share']:.2f} of windows) -> x{v['games_mult']:.2f} games", flush=True)
        res["bars"][str(bar)] = r
    (out / "probe.json").write_text(json.dumps(res, indent=1))
    print(f"[probe] -> {out / 'probe.json'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="verb", required=True)
    b = sub.add_parser("build")
    b.add_argument("--runs", required=True, help="comma list of run dirs (each ingested under data/trajectories/<name>)")
    b.add_argument("--out", required=True)
    b.add_argument("--ckpt", default=CKPT)
    b.add_argument("--batch", type=int, default=32)
    p = sub.add_parser("probe")
    p.add_argument("--out", required=True)
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--floor", type=float, default=0.1)
    p.add_argument("--l2", type=float, default=1e-3)
    a = ap.parse_args()
    build(a) if a.verb == "build" else probe(a)


if __name__ == "__main__":
    main()
