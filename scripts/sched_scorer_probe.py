#!/usr/bin/env python3
"""SCORER learning-curve probe (2026-09-05 diagnostic, pre-build): can a head
on the FROZEN trunk rank the certifier's arms the way the search ranked them?

Data: the harvest's arm spreads (one row per rolled-out window: every arm's
select/score composite vs the natural line) joined to the emission window
in the harvest store. Features per (window, arm): the trunk's [STATE] read-out
and the schedule key vectors of the arm's candidates (net._sched_keys — the
same key space the decode head uses), pooled: mean + sum + length. Target:
the arm's 8-roll mean composite (select + score halves). Model: a 2-layer MLP,
pairwise ranking loss within a window. Read: within-window Spearman on
holdout windows (game-hash holdout), top-1 hit rate, and the precision of a
margin gate (predicted top-arm margin > bar => the search also found an arm
>= θ) — at 25 / 50 / 100 % of training windows. The exact-arm head's curve
(sched_distill fit --label-frac) is the comparison.

Usage:
  uv run python scripts/sched_scorer_probe.py --ckpt data/training/m10-planner-distill-hand2/last.pt
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sched_certify_finish import _emission_window  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data/runs/sched-harvest-h1/harvest-manifest.json"


def spearman(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 3:
        return float("nan")
    ra = [sorted(a).index(x) for x in a]
    rb = [sorted(b).index(x) for x in b]
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else float("nan")


@torch.no_grad()
def featurize(args, dev) -> list[dict]:
    from anvil.bridge.featurize import Featurizer, store_wire_hist
    from anvil.store.trajectories import TrajectoryStore
    from anvil.training.dataset import collate, default_methods
    from anvil.training.train import build_net

    ck = torch.load(args.ckpt, map_location=dev, weights_only=False)
    cfg = ck["config"]
    net = build_net(cfg["embed"], cfg["pool_manifest"], len(default_methods()),
                    n_sa=cfg.get("sa_vocab_size", 0)).to(dev)
    net.load_compat(ck["model"])
    net.eval()
    feat = Featurizer(cfg["embed"], default_methods(), ability_table=str(REPO / "data/pool/ability-table.json"))
    m = json.loads(MANIFEST.read_text())
    windows = []
    for b in m["batches"]:
        st = TrajectoryStore(Path(b["store"]))
        spread_path = b["labels"].replace(".jsonl", ".spread.jsonl")
        arms_by_key = {}
        # arm labels from the sched_arms rows (the finish step's load_arms)
        from sched_certify_finish import load_arms
        arms_def = load_arms([str(Path(b["run"]) / "workers" / "inv-*" / "labels.jsonl")])
        for ln in open(spread_path):
            s = json.loads(ln)
            arms_by_key[(s["g"], s["t"])] = s
        by_game = defaultdict(list)
        for key, s in arms_by_key.items():
            by_game[key[0]].append(s)
        for g, sps in by_game.items():
            try:
                traj = st.game(g)
            except Exception:  # noqa: BLE001
                continue
            decs = traj.decisions
            for s in sps:
                win = _emission_window(decs, s["seat"], s["t"])
                if win is None:
                    continue
                emis_i, dec = win
                wire = dict(dec)
                if "hist" not in dec:
                    wire["hist"] = store_wire_hist(decs[:emis_i], dec.get("_pos", emis_i))
                try:
                    ex, aux = feat.example(wire, traj.header, "priority")
                except Exception:  # noqa: BLE001
                    continue
                opts = dec.get("opts") or []
                cand_of = {}
                for j, fo in enumerate(aux["cand_first_opt"]):
                    if j == 0 or fo < 0:
                        continue
                    cand_of.setdefault(str(opts[fo].get("sa") or "")[:60], j)
                defs = arms_def.get((s["g"], s["t"]), {}).get("arms", {})
                arms = []
                for a in s["arms"]:
                    if a["score_mean"] is None or a["select_mean"] is None:
                        continue
                    labels = defs.get(a["arm"], ("", []))[1]
                    idxs = [cand_of.get(lab[:60]) for lab in labels]
                    if any(i is None for i in idxs):
                        continue
                    target = (a["n_sel"] * a["select_mean"] + a["n_sco"] * a["score_mean"]) / max(1, a["n_sel"] + a["n_sco"])
                    arms.append({"arm": a["arm"], "idxs": idxs, "target": target,
                                 "score_mean": a["score_mean"]})
                if len(arms) < 3:
                    continue
                ex = {k: v for k, v in ex.items() if torch.is_tensor(v)}
                bt = collate([ex])
                bt = {k: (v.to(dev) if torch.is_tensor(v) else v) for k, v in bt.items()}
                card_vecs = net.cards(bt["ent_emb"])
                tokens, pad = net.assemble(card_vecs, bt)
                out = net.trunk(tokens, src_key_padding_mask=pad)
                state = out[:, 0]
                n_ent = bt["entities"].shape[1]
                ent_out = out[:, 2:2 + n_ent]
                # legal-prefix key space (drop the sched_ superset for the join)
                bl = {k: v for k, v in bt.items() if not k.startswith("sched_cand_")}
                keys, _vecs, _mask = net._sched_keys(ent_out, bl)
                keys = keys[0]  # (C, d)
                d = keys.shape[-1]
                feats, targets, scores, ids = [], [], [], []
                for a in arms:
                    if a["idxs"]:
                        kv = keys[torch.tensor(a["idxs"], device=dev)]
                        pooled = torch.cat([kv.mean(0), kv.sum(0)])
                    else:
                        pooled = torch.zeros(2 * d, device=dev)
                    feats.append(torch.cat([state[0], pooled, torch.tensor([len(a["idxs"])], device=dev, dtype=torch.float32)]))
                    targets.append(a["target"])
                    scores.append(a["score_mean"])
                    ids.append(a["arm"])
                windows.append({"key": (b["store"], s["g"], s["t"]), "x": torch.stack(feats).cpu(),
                                "y": torch.tensor(targets), "score": scores, "arm": ids,
                                "certified": s["certified"]})
    return windows


def _slice(x: torch.Tensor, feats: str, d: int) -> torch.Tensor:
    """feature ablation: all | arms (pooled keys + len only) | state (state only)"""
    if feats == "arms":
        return x[:, d:]
    if feats == "state":
        return x[:, :d]
    return x


def train_eval(windows: list[dict], frac: float, seed: int, dev, epochs: int = 60,
               arch: str = "mlp", feats: str = "all", d_state: int = 0) -> dict:
    rng = random.Random(seed)
    def hold(w):
        h = hashlib.blake2b(repr(w["key"][:2]).encode(), digest_size=8).digest()
        return int.from_bytes(h, "big") / 2**64 < 0.25
    test = [w for w in windows if hold(w)]
    train = [w for w in windows if not hold(w)]
    rng.shuffle(train)
    train = train[: max(8, int(len(train) * frac))]
    d_in = _slice(windows[0]["x"], feats, d_state).shape[-1]
    torch.manual_seed(seed)
    if arch == "linear":
        net = torch.nn.Linear(d_in, 1).to(dev)
        opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-1)
    else:
        net = torch.nn.Sequential(torch.nn.Linear(d_in, 256), torch.nn.GELU(), torch.nn.Dropout(0.1),
                                  torch.nn.Linear(256, 64), torch.nn.GELU(), torch.nn.Linear(64, 1)).to(dev)
        opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-2)
    for _ in range(epochs):
        rng.shuffle(train)
        net.train()
        for w in train:
            x = _slice(w["x"], feats, d_state).to(dev)
            y = w["y"].to(dev)
            p = net(x).squeeze(-1)
            # pairwise ranking within the window + a small MSE anchor on scale
            diff_p = p.unsqueeze(0) - p.unsqueeze(1)
            diff_y = y.unsqueeze(0) - y.unsqueeze(1)
            pair = torch.nn.functional.softplus(-diff_p * torch.sign(diff_y)) * (diff_y.abs() > 0.5).float()
            loss = pair.sum() / max(1.0, (diff_y.abs() > 0.5).float().sum().item()) + 0.05 * ((p - y) ** 2).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
    net.eval()
    rhos, top1, gate_tp, gate_fp, cert_n = [], 0, 0, 0, 0
    with torch.no_grad():
        for w in test:
            p = net(_slice(w["x"], feats, d_state).to(dev)).squeeze(-1).cpu().tolist()
            y = w["y"].tolist()
            rhos.append(spearman(p, y))
            top1 += int(max(range(len(p)), key=lambda i: p[i]) == max(range(len(y)), key=lambda i: y[i]))
            # margin gate: predicted best arm margin (vs 0 = natural) > 2 => the search certified an arm
            pred_margin = max(p)
            found = max(w["score"]) >= 2.0
            cert_n += int(found)
            if pred_margin > 2.0:
                gate_tp += int(found)
                gate_fp += int(not found)
    rhos = [r for r in rhos if r == r]
    return {"frac": frac, "n_train": len(train), "n_test": len(test),
            "spearman": round(sum(rhos) / max(1, len(rhos)), 3),
            "top1": round(top1 / max(1, len(test)), 3),
            "gate_precision": round(gate_tp / max(1, gate_tp + gate_fp), 3), "gate_fired": gate_tp + gate_fp,
            "gate_recall": round(gate_tp / max(1, cert_n), 3), "windows_with_certified": cert_n}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=str(REPO / "data/training/m10-planner-distill-hand2/last.pt"))
    ap.add_argument("--out", default=str(REPO / "data/runs/sched-scorer-probe.json"))
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--arch", choices=["mlp", "linear"], default="mlp")
    ap.add_argument("--feats", choices=["all", "arms", "state"], default="all")
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    windows = featurize(a, dev)
    n_arms = sum(len(w["arm"]) for w in windows)
    print(f"[scorer] {len(windows)} windows, {n_arms} (window, arm) pairs featurized")
    d_state = (windows[0]["x"].shape[-1] - 1) // 3  # [state d | mean d | sum d | len]
    res = {"windows": len(windows), "pairs": n_arms, "arch": a.arch, "feats": a.feats, "curve": []}
    for frac in (0.25, 0.5, 1.0):
        rs = [train_eval(windows, frac, seed, dev, arch=a.arch, feats=a.feats, d_state=d_state)
              for seed in range(a.seeds)]
        agg = {k: (round(sum(r[k] for r in rs) / len(rs), 3) if isinstance(rs[0][k], float) else rs[0][k]) for k in rs[0]}
        res["curve"].append(agg)
        print(f"[scorer] frac {frac}: {agg}")
    # chance references: random ranking Spearman ~0, top-1 ~ 1/n_arms
    res["chance_top1"] = round(sum(1 / len(w["arm"]) for w in windows) / len(windows), 3)
    json.dump(res, open(a.out, "w"), indent=2)
    print(f"[scorer] chance top-1 {res['chance_top1']} -> {a.out}")


if __name__ == "__main__":
    main()
