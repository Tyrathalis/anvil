#!/usr/bin/env python3
"""M9 D6 R1 — the aux-target probe (m9-d6-plan-latent-spec §5, pins
PRE-DATA in the spec's R1 block).

Question: from the frozen trunk's representation of a turn-group's first
own-seat window (the emission point), are the candidate aux targets
predictable above the obs-arithmetic baseline (ADR-0043 reconstruction
discipline)? Decides what the plan latent's dense emission loss predicts —
or, if neither target clears, that the formulation has no premise and the
build does not start.

  dump   stores + frozen ckpt -> per (seat, turn) group: [STATE]/[PLAN]
         vectors at the emission window + obs-arithmetic features +
         targets (a) realized action summary, (c) end-of-turn delta.
  probe  the pinned arm ladder (base -> arith -> [STATE] -> [STATE]+[PLAN])
         against the pinned gates; report JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

SUMMARY_BITS = ["land_played", "any_ability", "attacked"]
DELTA_AXES = ["own_life", "opp_life", "own_hand", "own_board", "own_creatures", "own_power"]
VOCAB_TOP = 256
MIN_SUPPORT = 50
GATE_A = {"margin": 0.03, "floor": 0.60}
GATE_C = {"margin": 0.05, "floor": 0.15}


def _arith(obs: dict, seat: int) -> list[float]:
    pl = obs["players"]
    o = 1 - seat
    f = [float(obs["glob"].get("turn", 0))]
    for s in (seat, o):
        p = pl[s]
        f += [float(p.get("life", 0)), float(p.get("hand", 0)),
              float(p.get("lib", 0)), float((p.get("cmdcast") or [0])[0])]
    for c in (seat, o):
        ents = [e for e in obs.get("ents") or [] if e.get("c") == c]
        bf = [e for e in ents if e.get("z") == "battlefield"]
        cr = [e for e in bf if e.get("pt")]
        f += [float(len(bf)), float(len(cr)),
              float(sum(e["pt"][0] for e in cr)),
              float(sum(1 for e in bf if not e.get("tap"))),
              float(sum(1 for e in ents if e.get("z") == "command"))]
    return f


def _axes(obs: dict, seat: int) -> dict:
    pl = obs["players"]
    o = 1 - seat
    bf = [e for e in obs.get("ents") or [] if e.get("c") == seat and e.get("z") == "battlefield"]
    cr = [e for e in bf if e.get("pt")]
    return {"own_life": pl[seat].get("life", 0), "opp_life": pl[o].get("life", 0),
            "own_hand": pl[seat].get("hand", 0), "own_board": len(bf),
            "own_creatures": len(cr), "own_power": sum(e["pt"][0] for e in cr)}


def dump(args) -> None:
    import torch

    from anvil.ante.ledger import ValueEvaluator
    from anvil.store.trajectories import TrajectoryStore
    from anvil.training.dataset import collate

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ev = ValueEvaluator(args.ckpt)

    rows, exs = [], []
    for store in args.stores:
        ts = TrajectoryStore(Path(store))
        name = Path(store).name
        for traj in ts.games(skip_undecodable=True):
            g = traj.header["g"]
            for seat in (0, 1):
                groups: dict[int, list] = defaultdict(list)
                dec_idx: dict[int, int] = {}
                for i, dec in enumerate(traj.decisions):
                    if dec.get("p") == seat and dec.get("t", 0) >= 1:
                        groups[dec["t"]].append(dec)
                        dec_idx[id(dec)] = i
                emis = {}
                for t, decs in groups.items():
                    first = next((d for d in decs if d.get("obs")), None)
                    if first is not None:
                        emis[t] = first
                for t, decs in sorted(groups.items()):
                    if t not in emis:
                        continue
                    sas, bits = [], dict.fromkeys(SUMMARY_BITS, 0)
                    for d in decs:
                        if d.get("m") == "chooseSpellAbilityToPlay" and d.get("ret"):
                            for r in d["ret"]:
                                kind = r.get("kind")
                                if kind == "land":
                                    bits["land_played"] = 1
                                elif kind == "ability":
                                    bits["any_ability"] = 1
                                if r.get("sa"):
                                    sas.append(r["sa"])
                        if d.get("m") == "declareAttackers":
                            bits["attacked"] = 1
                    obs0 = emis[t]["obs"]
                    nxt = emis.get(t + 1)
                    delta = None
                    if nxt is not None:
                        a0, a1 = _axes(obs0, seat), _axes(nxt["obs"], seat)
                        delta = {k: a1[k] - a0[k] for k in DELTA_AXES}
                    rows.append({"store": name, "g": g, "seat": seat, "t": t,
                                 "sas": sas, **bits, "delta": delta,
                                 "arith": _arith(obs0, seat)})
                    idx = dec_idx[id(emis[t])]
                    exs.append(ev.example(emis[t], traj.header, seat,
                                          traj.decisions[:idx]))
    print(f"{len(rows)} turn-groups from {len(args.stores)} stores")

    feats_s, feats_p = [], []

    @torch.no_grad()
    def capture(batch_exs):
        chunk = collate(batch_exs)
        chunk = {k: v.to(ev.device) for k, v in chunk.items()}
        with torch.autocast(ev.device, dtype=torch.bfloat16):
            card_vecs = ev.net.cards(chunk["ent_emb"])
            tokens, pad = ev.net.assemble(card_vecs, chunk)
            o = ev.net.trunk(tokens, src_key_padding_mask=pad)
        feats_s.append(o[:, 0].float().cpu().numpy())
        feats_p.append(o[:, 1].float().cpu().numpy())

    for i in range(0, len(exs), ev.batch):
        capture(exs[i:i + ev.batch])
    np.savez_compressed(out / "features.npz",
                        state=np.concatenate(feats_s),
                        plan=np.concatenate(feats_p))
    with open(out / "rows.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"-> {out}/features.npz + rows.jsonl")


def _split(rows) -> np.ndarray:
    """True = train. Deterministic game-grouped 80/20."""
    def h(r):
        return int(hashlib.sha1(f"{r['store']}:{r['g']}".encode()).hexdigest(), 16) % 5
    return np.array([h(r) != 0 for r in rows])


def _auc(y, s) -> float:
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s))


def _fit_predict(xtr, ytr, xte, alphas=(1.0, 10.0, 100.0)) -> np.ndarray:
    from sklearn.linear_model import Ridge

    best, best_err = None, None
    n = len(xtr)
    cut = int(n * 0.8)
    for a in alphas:
        m = Ridge(alpha=a).fit(xtr[:cut], ytr[:cut])
        err = float(np.mean((m.predict(xtr[cut:]) - ytr[cut:]) ** 2))
        if best_err is None or err < best_err:
            best, best_err = a, err
    m = Ridge(alpha=best).fit(xtr, ytr)
    return m.predict(xte)


def probe(args) -> None:
    from scipy.stats import spearmanr

    out = Path(args.dump)
    rows = [json.loads(l) for l in open(out / "rows.jsonl")]
    fz = np.load(out / "features.npz")
    state, plan = fz["state"], fz["plan"]
    assert len(rows) == len(state)
    tr = _split(rows)
    arith = np.array([r["arith"] for r in rows])
    arith = (arith - arith[tr].mean(0)) / (arith[tr].std(0) + 1e-6)
    arms = {"arith": arith, "state": state,
            "state_plan": np.concatenate([state, plan], axis=1)}

    # ---- (a) action summary: probe-local vocab from TRAIN only ----
    cnt = Counter(sa for r, t in zip(rows, tr) if t for sa in set(r["sas"]))
    vocab = [sa for sa, c in cnt.most_common(VOCAB_TOP) if c >= MIN_SUPPORT]
    classes = vocab + SUMMARY_BITS
    Y = np.zeros((len(rows), len(classes)), dtype=np.float32)
    for i, r in enumerate(rows):
        ss = set(r["sas"])
        for j, sa in enumerate(vocab):
            Y[i, j] = 1.0 if sa in ss else 0.0
        for j, b in enumerate(SUMMARY_BITS):
            Y[i, len(vocab) + j] = float(r[b])
    report = {"n": len(rows), "n_train": int(tr.sum()), "classes": len(classes)}
    res_a = {}
    for name, X in arms.items():
        preds = _fit_predict(X[tr], Y[tr], X[~tr])
        aucs = []
        for j in range(len(classes)):
            yte = Y[~tr, j]
            if 0 < yte.sum() < len(yte):
                aucs.append(_auc(yte, preds[:, j]))
        res_a[name] = float(np.mean(aucs))
    report["a_macro_auc"] = res_a
    ga = res_a["state_plan"] - res_a["arith"] >= GATE_A["margin"] \
        and res_a["state_plan"] >= GATE_A["floor"]
    report["a_gate"] = {"pass": bool(ga), **GATE_A}

    # ---- (c) end-of-turn delta ----
    has_c = np.array([r["delta"] is not None for r in rows])
    Yc = np.array([[r["delta"][k] for k in DELTA_AXES] if r["delta"] else
                   [0.0] * len(DELTA_AXES) for r in rows], dtype=np.float32)
    res_c = {}
    trc, tec = tr & has_c, (~tr) & has_c
    for name, X in arms.items():
        preds = _fit_predict(X[trc], Yc[trc], X[tec])
        sp = [float(spearmanr(Yc[tec, j], preds[:, j]).statistic)
              for j in range(len(DELTA_AXES))]
        res_c[name] = {"mean": float(np.mean(sp)),
                       "axes": dict(zip(DELTA_AXES, [round(s, 4) for s in sp]))}
    report["c_spearman"] = res_c
    gc = res_c["state_plan"]["mean"] - res_c["arith"]["mean"] >= GATE_C["margin"] \
        and res_c["state_plan"]["mean"] >= GATE_C["floor"]
    report["c_gate"] = {"pass": bool(gc), **GATE_C}

    sel = ("joint" if ga and gc else "a" if ga else "c" if gc else "NONE")
    report["selection"] = sel
    (out / "probe-read.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"n={len(rows)} (train {int(tr.sum())}), classes={len(classes)}, "
          f"c-rows={int(has_c.sum())}")
    print("(a) macro-AUC:  " + "  ".join(f"{k}={v:.4f}" for k, v in res_a.items())
          + f"  -> gate {'PASS' if ga else 'fail'}")
    print("(c) mean rho:   " + "  ".join(f"{k}={v['mean']:.4f}" for k, v in res_c.items())
          + f"  -> gate {'PASS' if gc else 'fail'}")
    print(f"SELECTION: {sel}")
    print(f"-> {out}/probe-read.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump")
    d.add_argument("--stores", nargs="+", required=True)
    d.add_argument("--ckpt", required=True)
    d.add_argument("--out", required=True)
    d.set_defaults(fn=dump)
    p = sub.add_parser("probe")
    p.add_argument("--dump", required=True)
    p.set_defaults(fn=probe)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
