"""M12 Build 1 — the masked value head trained INSIDE the shared trunk on
banked rollout labels (m12-plan.md Build 1; ADR-0103).

The day-zero checkpoint for Build 2's four-arm read: iter-019's policy heads
kept in place (a KL anchor to the frozen teacher on live priority windows),
the value head + the top-N trunk layers moved by three label families that
already sit on disk in the iter-019 era (obs sv=2, pool cf2ca6ba):

  state    labelset-c2-v3 c2 rows — K=8 rollout winrate at the first
           obs-carrying decision of turn t (the ADR-0036/0041 benchmark;
           frozen holdout = the STATE-RANKING read). RankNet pairs
           (|dwr|-weighted, gate 0.2) + a 0.05 BCE anchor on wr.
  leaf     the cl2 completions' eot / h2 windows per (window, arm, roll):
           ~108K post-action states with (i) the full-vis critic's value
           already banked in lookahead-read.json — distilled into the
           masked head (soft BCE) — and (ii) the paired h2 composite per
           (arm, roll) — RankNet over arms within a (window, roll, horizon)
           group. The ONE-PLY read (masked / eot / K=1 vs comp8, the
           ADR-0098 cell at 0.277) is CROSS-FIT: windows split into folds by
           game hash, each fold's read comes from the model that never saw
           it, pooled over folds at the full 650-window precision.
  outcome  priority windows sampled from the m9-rebaseline stores (iter-019
           vs the heuristic, 2 x 1,000 games, terminal outcomes): BCE on won
           + the policy anchor KL(teacher || student) on the pointer logits.

Pre-registered (m12-plan Build 1, ADR-0101 §3 / ADR-0102 item 6): GO at
one-ply >= 0.35 and/or state-ranking holdout mean >= 0.50; KILL if neither
clears 0.32. Mint per-arm rows carry no stored post-action state and are not
used; the drill fork points are already rows of the labelset.

Usage:
  uv run python -m anvil.training.value_pretrain bank --out data/runs/m12-build1
  uv run python -m anvil.training.value_pretrain fit  --out data/runs/m12-build1 --fold 0
  uv run python -m anvil.training.value_pretrain fit  --out data/runs/m12-build1 --build \\
      --ckpt-out data/training/m12-build1
  uv run python -m anvil.training.value_pretrain read --out data/runs/m12-build1
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import random
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
CKPT = "data/training/d6-run11/iter-019/train/last.pt"
LABELSET = "data/runs/labelset-c2-v3/dataset.jsonl"
CL2_READ = "data/runs/critic-lookahead-cl2/lookahead-read.json"
CL2_FORKS = "data/trajectories/critic-lookahead-cl2-forks"
OUTCOME_STORES = (
    "data/trajectories/m9-rebaselinearm-s0-20260821-164002",
    "data/trajectories/m9-rebaselinearm-s1-20260821-170608",
)
ERA = "c2"
K_ROLLS = 8
ROLLS = tuple(range(K_ROLLS))
N_FOLDS = 5
PAIR_GATE_WR = 0.2  # K=8 labels quantize at 1/8; one-step pairs are noise
PAIR_GATE_COMP = 1.0  # composite in dev units (creatures + lands - hand ...)
COMP_SCALE = 6.0  # pair weight = min(|dcomp|, COMP_SCALE) / COMP_SCALE
BARS = {"oneply_go": 0.35, "state_go": 0.50, "kill": 0.32}
HEADLINE = "eot/k1"


# ------------------------------------------------------------- splits


def _h(s: str) -> bytes:
    return hashlib.sha256(s.encode()).digest()


def held_out(store: str, g: int) -> bool:
    """The frozen holdout of the state benchmark — identical to
    critic_calibration._held_out / frozen_probe._held_out."""
    return _h(f"{store}:{g}")[0] % 5 == 0


def inner_val(game: str) -> bool:
    """unfreeze_probe._inner_val — game-grouped early-stop split."""
    return _h(f"uvval:{game}")[0] % 7 == 0


def leaf_fold(store_base: str, g: int) -> int:
    return _h(f"b1fold:{store_base}:{g}")[0] % N_FOLDS


def leaf_inner(store_base: str, g: int) -> bool:
    return _h(f"b1inner:{store_base}:{g}")[0] % 8 == 0


def outcome_held(store_base: str, g: int) -> bool:
    return _h(f"b1out:{store_base}:{g}")[0] % 5 == 0


def seat_of(store: str) -> int:
    if "-s0-" in store:
        return 0
    if "-s1-" in store:
        return 1
    raise ValueError(f"no seat marker in store name: {store}")


def spearman(a, b) -> float:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra, rb = ra - ra.mean(), rb - rb.mean()
    den = math.sqrt((ra**2).sum() * (rb**2).sum())
    return float((ra * rb).sum() / den) if den > 0 else float("nan")


# ------------------------------------------------------------- featurize


def _evaluator(full_vis: bool | None = False):
    from anvil.ante.ledger import ValueEvaluator

    return ValueEvaluator(str(REPO / CKPT), full_vis=full_vis)


def fork_example(ev, dec: dict, header: dict, perspective: int) -> dict:
    """critic_lookahead_read.Critic.example — the fork frame's own wire
    history instead of a store-side reconstruction."""
    import torch

    from anvil.bridge.featurize import wire_history
    from anvil.encoder.transform import HISTORY_K, assemble

    out = assemble(
        dec,
        header,
        perspective=perspective,
        history=wire_history(dec.get("hist"), perspective),
        full_vis=ev.full_vis,
    )
    ex = ev.example(dec, header, perspective, [])
    row_of = out["entity_row_of"]
    hist = np.full((HISTORY_K, 3), -1, dtype=np.int64)
    for j, h in enumerate(out["history"][-HISTORY_K:]):
        hist[j] = (ev.methods.id(h["m"]), h["self"], row_of.get(h["e"], -1))
    ex["history"] = torch.from_numpy(hist)
    return ex


def pick_windows(decs: list[dict], tt: int) -> dict[str, dict | None]:
    """eot = first obs-carrying decision of turn tt+1; h2 = the completion's
    last obs-carrying decision (critic_lookahead_read._pick_windows)."""
    eot = last = None
    for d in decs:
        obs = d.get("obs")
        if not obs:
            continue
        turn = obs.get("glob", {}).get("turn", -1)
        if eot is None and turn >= tt + 1:
            eot = d
        last = d
    return {"eot": eot, "h2": last}


# ------------------------------------------------------------- bank


def bank_state(ev, out_dir: Path, smoke: int | None) -> None:
    """(store, g, t) -> masked-path window at the first obs-carrying decision
    of turn t (unfreeze_probe.collect_examples, loud on any miss)."""
    import torch

    from anvil.store.trajectories import TrajectoryStore

    rows = [json.loads(ln) for ln in (REPO / LABELSET).open()]
    rows = [r for r in rows if r["era"] == ERA]
    if smoke:
        rows = rows[:smoke]
    positions = sorted({(r["store"], r["g"], r["t"]) for r in rows})
    by_store: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for store, g, t in positions:
        by_store[store].append((g, t))
    keys, exs, missed = [], [], []
    t0 = time.time()
    for store, wants in sorted(by_store.items()):
        ts = TrajectoryStore(REPO / "data/trajectories" / store)
        seat = seat_of(store)
        for g in sorted({g for g, _ in wants}):
            traj = ts.game(g)
            first_of_turn: dict[int, int] = {}
            seen = -1
            for i, dec in enumerate(traj.decisions):
                obs = dec.get("obs")
                if obs is None:
                    continue
                turn = obs["glob"].get("turn", 0)
                if turn < 1 or turn == seen:
                    continue
                seen = turn
                first_of_turn[turn] = i
            for g2, t in wants:
                if g2 != g:
                    continue
                i = first_of_turn.get(t)
                if i is None:
                    missed.append((store, g, t))
                    continue
                keys.append(f"{store}:{g}:{t}")
                exs.append(ev.example(traj.decisions[i], traj.header, seat, traj.decisions[:i]))
            del traj
    if missed:
        raise SystemExit(
            f"[bank state] {len(missed)} positions missed the turn join, e.g. {missed[:3]}"
        )
    key_idx = {k: i for i, k in enumerate(keys)}
    meta = [
        {
            "idx": key_idx[f"{r['store']}:{r['g']}:{r['t']}"],
            "wr": r["wr"],
            "game": f"{r['store']}:{r['g']}",
            "src": r["src"],
            "holdout": held_out(r["store"], r["g"]),
            "inner": inner_val(f"{r['store']}:{r['g']}"),
        }
        for r in rows
    ]
    torch.save(
        {"examples": exs, "meta": meta, "ckpt": CKPT, "labelset": LABELSET},
        out_dir / "bank-state.pt",
    )
    print(
        f"[bank state] {len(rows)} rows -> {len(exs)} windows "
        f"(holdout {sum(m['holdout'] for m in meta)}) in {time.time() - t0:.0f}s",
        flush=True,
    )


def bank_leaf(ev, out_dir: Path, smoke: int | None) -> None:
    """Every cl2 completion's eot + h2 window from the acting seat, with the
    banked full-vis value and the paired composite. Streams one completion
    at a time (the 09-06 OOM lesson); windows without a banked value (the
    completion ended inside the arm's turn) are skipped."""
    import torch

    from anvil.store.trajectories import TrajectoryStore

    d = json.loads((REPO / CL2_READ).read_text())
    windows = d["windows"]
    if smoke:
        windows = windows[:smoke]
    comp: dict[tuple, list[tuple]] = defaultdict(list)
    for ln in (REPO / CL2_FORKS / "games.jsonl").open():
        r = json.loads(ln)
        fk = r.get("fork") or {}
        if "a" in fk:
            comp[(fk["pg"], fk["tt"])].append((fk["a"], fk["r"], r["i"]))
    st = TrajectoryStore(REPO / CL2_FORKS)
    exs, meta, wmeta = [], [], []
    tally: dict[str, int] = defaultdict(int)
    t0 = time.time()
    for wi, w in enumerate(windows):
        base = Path(w["store"]).name
        wmeta.append(
            {
                "wi": wi,
                "store": base,
                "g": w["g"],
                "t": w["t"],
                "seat": w["seat"],
                "fold": leaf_fold(base, w["g"]),
                "inner": leaf_inner(base, w["g"]),
                "certified_lane": bool(w.get("certified_lane")),
                "comp": w["comp"],
            }
        )
        void = {str(a) for a in w.get("void", [])}
        for a, r, gid in comp.get((w["g"], w["t"]), []):
            if str(a) in void:
                continue
            try:
                traj = st.game(gid)
            except Exception as e:  # noqa: BLE001
                tally[f"undecodable_{type(e).__name__}"] += 1
                continue
            picks = pick_windows(traj.decisions, w["t"])
            for hz, dec in picks.items():
                fv = w["vals"]["fullvis"].get(f"{a}:{r}:{hz}")
                if dec is None or fv is None:
                    tally[f"no_{hz}"] += 1
                    continue
                try:
                    ex = fork_example(ev, dec, traj.header, w["seat"])
                except Exception as e:  # noqa: BLE001
                    tally[f"featurize_{type(e).__name__}"] += 1
                    continue
                exs.append(ex)
                meta.append(
                    {
                        "wi": wi,
                        "arm": int(a),
                        "roll": int(r),
                        "hz": hz,
                        "fv": float(fv),
                        "comp": w["comp"].get(f"{a}:{r}"),
                    }
                )
            del traj
        if (wi + 1) % 50 == 0:
            print(
                f"[bank leaf] {wi + 1} windows, {len(exs)} leaves, {time.time() - t0:.0f}s",
                flush=True,
            )
    torch.save(
        {"examples": exs, "meta": meta, "windows": wmeta, "ckpt": CKPT, "tally": dict(tally)},
        out_dir / "bank-leaf.pt",
    )
    print(
        f"[bank leaf] {len(windows)} windows -> {len(exs)} leaves, tally {dict(tally)}, {time.time() - t0:.0f}s",
        flush=True,
    )


def bank_outcome(out_dir: Path, per_store: int, keep: float, seed: int, smoke: int | None) -> None:
    """Priority windows with terminal outcomes + full candidate fields (the
    KL anchor needs the pointer set), sampled from the rebaseline stores."""
    import torch

    from anvil.training.dataset import PriorityWindows, default_methods

    ck = torch.load(REPO / CKPT, map_location="cpu", weights_only=False)
    cfg = ck["config"]
    rng = random.Random(seed)
    exs, meta = [], []
    t0 = time.time()
    for store in OUTCOME_STORES:
        base = Path(store).name
        ds = PriorityWindows(
            str(REPO / store), cfg["embed"], default_methods(), tasks={"priority"}, seed=seed
        )
        n_store = n_games = 0
        cap = smoke or per_store
        from anvil.store.trajectories import open_store

        st = open_store(ds.store_dir)
        games = ds._epoch_games(st)
        for g in games:
            n_games += 1
            for ex in ds._examples(st, g):
                if not int(ex["has_outcome"]):
                    continue
                if rng.random() > keep:
                    continue
                exs.append(ex)
                meta.append({"store": base, "g": g, "held": outcome_held(base, g)})
                n_store += 1
                if n_store >= cap:
                    break
            if n_store >= cap:
                break
        print(
            f"[bank outcome] {base}: {n_store} windows from {n_games} games, {time.time() - t0:.0f}s",
            flush=True,
        )
    torch.save(
        {"examples": exs, "meta": meta, "ckpt": CKPT, "stores": list(OUTCOME_STORES)},
        out_dir / "bank-outcome.pt",
    )
    print(f"[bank outcome] {len(exs)} windows (held {sum(m['held'] for m in meta)})", flush=True)


def bank(args: argparse.Namespace) -> None:
    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    ev = _evaluator(False)
    assert not ev.full_vis, "Build 1 trains the MASKED path"
    fams = set(args.families.split(","))
    if "state" in fams:
        bank_state(ev, out_dir, args.smoke)
    if "leaf" in fams:
        bank_leaf(ev, out_dir, args.smoke)
    if "outcome" in fams:
        bank_outcome(out_dir, args.outcome_per_store, args.outcome_keep, args.seed, args.smoke)


# ------------------------------------------------------------- model


def load_net(device: str):
    import torch

    from anvil.training.dataset import default_methods
    from anvil.training.train import build_net

    ck = torch.load(REPO / CKPT, map_location=device, weights_only=False)
    cfg = ck["config"]
    net = build_net(
        cfg["embed"], cfg["pool_manifest"], len(default_methods()), n_sa=cfg.get("sa_vocab_size", 0)
    ).to(device)
    net.load_compat(ck["model"])
    return net, ck


def set_trainable(net, unfreeze: str) -> int:
    n_layers = len(net.trunk.layers)
    if unfreeze == "all":
        top = set(range(n_layers))
    else:
        top = set(range(n_layers - int(unfreeze), n_layers))
    for name, p in net.named_parameters():
        p.requires_grad = name.startswith("value_head") or any(
            name.startswith(f"trunk.layers.{i}.") for i in top
        )
    return sum(p.numel() for p in net.parameters() if p.requires_grad)


def value_logits(net, chunk: dict):
    """The cheap path: cards -> assemble -> trunk -> value head."""
    card_vecs = net.cards(chunk["ent_emb"])
    tokens, pad = net.assemble(card_vecs, chunk)
    h = net.trunk(tokens, src_key_padding_mask=pad)
    return net.value_head(h[:, 0]).squeeze(-1)


def _to(chunk: dict, device: str) -> dict:
    return {k: v.to(device, non_blocking=True) for k, v in chunk.items()}


def scores(net, examples: list, idxs, device: str, batch: int) -> np.ndarray:
    import torch

    from anvil.training.dataset import collate

    net.eval()
    out = np.empty(len(idxs), dtype=np.float64)
    with torch.no_grad():
        for i in range(0, len(idxs), batch):
            chunk = _to(collate([examples[j] for j in idxs[i : i + batch]]), device)
            with torch.autocast(device, dtype=torch.bfloat16):
                v = value_logits(net, chunk)
            out[i : i + len(v)] = v.float().cpu().numpy()
    return out


def rank_loss(s, y, gate: float, scale: float | None):
    """RankNet pairwise logistic over pairs with y_i - y_j > gate, weighted
    by the gap (clipped at scale when given)."""
    import torch

    dy = y.unsqueeze(0) - y.unsqueeze(1)
    mask = dy > gate
    if not mask.any():
        return None
    ds = s.unsqueeze(0) - s.unsqueeze(1)
    w = dy[mask]
    if scale:
        w = w.clamp(max=scale) / scale
    return (torch.nn.functional.softplus(-ds[mask]) * w).sum() / w.sum()


# ------------------------------------------------------------- reads


def oneply_cells(vals: dict[tuple, float], windows: list[dict], wis: list[int]) -> dict:
    """critic_lookahead_read's cells on a set of windows. vals: (wi, arm,
    roll, hz) -> V. Returns per-cell per-window rhos (pooled by `read`)."""

    def pred(w, hz, roll_set):
        out = {}
        for a in sorted({int(k.split(":")[0]) for k in w["comp"]}):
            ds = []
            for r in roll_set:
                va, vn = vals.get((w["wi"], a, r, hz)), vals.get((w["wi"], 0, r, hz))
                if va is not None and vn is not None:
                    ds.append(va - vn)
            if ds:
                out[a] = sum(ds) / len(ds)
        return out

    def target(w, roll_set):
        out = {}
        for a in sorted({int(k.split(":")[0]) for k in w["comp"]}):
            cs = [w["comp"][f"{a}:{r}"] for r in roll_set if f"{a}:{r}" in w["comp"]]
            if cs:
                out[a] = sum(cs) / len(cs)
        return out

    cells = {}
    for hz in ("eot", "h2"):
        for name, rs in (("k1", (0,)), ("k8", ROLLS)):
            rhos, top1, lt3, const = [], [], 0, 0
            for wi in wis:
                w = windows[wi]
                p, y = pred(w, hz, rs), target(w, ROLLS)
                arms = [a for a in p if a in y]
                if len(arms) < 3:
                    lt3 += 1
                    continue
                rho = spearman([p[a] for a in arms], [y[a] for a in arms])
                if rho != rho:
                    const += 1
                    continue
                rhos.append((wi, rho))
                top1.append(int(max(arms, key=lambda a: p[a]) == max(arms, key=lambda a: y[a])))
            cells[f"{hz}/{name}"] = {"rhos": rhos, "top1": top1, "n_lt3": lt3, "n_const": const}
    return cells


def summarize_cell(cell: dict) -> dict:
    r = [x[1] for x in cell["rhos"]]
    n = len(r)
    if n == 0:
        return {"n": 0}
    mean = sum(r) / n
    se = (sum((x - mean) ** 2 for x in r) / max(1, n - 1)) ** 0.5 / n**0.5 if n > 1 else None
    return {
        "n": n,
        "spearman_mean": round(mean, 4),
        "spearman_se": round(se, 4) if se is not None else None,
        "spearman_median": round(sorted(r)[n // 2], 4),
        "top1": round(sum(cell["top1"]) / n, 3),
        "n_lt3": cell["n_lt3"],
        "n_const": cell["n_const"],
    }


def leaf_values(net, leaf: dict, wis: set[int], device: str, batch: int) -> dict[tuple, float]:
    idx = np.array([i for i, m in enumerate(leaf["meta"]) if m["wi"] in wis])
    if len(idx) == 0:
        return {}
    v = scores(net, leaf["examples"], idx, device, batch)
    out = {}
    for i, s in zip(idx, v):
        m = leaf["meta"][i]
        out[(m["wi"], m["arm"], m["roll"], m["hz"])] = float(1 / (1 + math.exp(-s)))
    return out


def drift_read(net, teacher, outcome: dict, idx: np.ndarray, device: str, batch: int) -> dict:
    """Policy drift vs the frozen teacher on held-out priority windows: mean
    KL(teacher || student), argmax agreement, and value BCE/AUC on won."""
    import torch
    import torch.nn.functional as F

    from anvil.training.dataset import collate

    net.eval()
    if len(idx) == 0:
        return {"n": 0}
    kls, agree, bces, probs, wons = [], [], [], [], []
    with torch.no_grad():
        for i in range(0, len(idx), batch):
            chunk = _to(collate([outcome["examples"][j] for j in idx[i : i + batch]]), device)
            with torch.autocast(device, dtype=torch.bfloat16):
                so, to = net(chunk), teacher(chunk)
            sl, tl = so["policy_logits"].float(), to["policy_logits"].float()
            lp_s, lp_t = F.log_softmax(sl, -1), F.log_softmax(tl, -1)
            kl = (lp_t.exp() * (lp_t - lp_s)).masked_fill(~chunk["cand_mask"], 0).sum(-1)
            kls += kl.tolist()
            agree += (sl.argmax(-1) == tl.argmax(-1)).float().tolist()
            v = so["value_logit"].float()
            bces += F.binary_cross_entropy_with_logits(
                v, chunk["won"].float(), reduction="none"
            ).tolist()
            probs += torch.sigmoid(v).tolist()
            wons += chunk["won"].tolist()
    p, y = np.array(probs), np.array(wons)
    pos = y == 1
    n1, n0 = int(pos.sum()), int((~pos).sum())
    auc = None
    if n1 and n0:
        r = np.empty(len(p))
        r[np.argsort(p, kind="stable")] = np.arange(1, len(p) + 1)
        auc = float((r[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
    return {
        "n": len(idx),
        "kl_mean": round(float(np.mean(kls)), 5),
        "kl_p90": round(float(np.quantile(kls, 0.9)), 5),
        "argmax_agree": round(float(np.mean(agree)), 4),
        "value_bce": round(float(np.mean(bces)), 4),
        "value_auc": round(auc, 4) if auc is not None else None,
    }


# ------------------------------------------------------------- fit


def fit(args: argparse.Namespace) -> None:
    import torch
    import torch.nn.functional as F

    from anvil.training.dataset import collate

    out_dir = REPO / args.out
    device = "cuda"
    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    tag = "build" if args.build else f"fold{args.fold}"
    log = (out_dir / f"fit-{tag}.jsonl").open("w")

    state = torch.load(out_dir / "bank-state.pt", weights_only=False)
    leaf = torch.load(out_dir / "bank-leaf.pt", weights_only=False)
    outcome = torch.load(out_dir / "bank-outcome.pt", weights_only=False)
    print(
        f"[fit {tag}] banks: state {len(state['examples'])} leaf {len(leaf['examples'])} outcome {len(outcome['examples'])}",
        flush=True,
    )

    # ---- splits
    sm = state["meta"]
    s_ho = np.array([m["holdout"] for m in sm])
    s_in = np.array([m["inner"] for m in sm]) & ~s_ho
    s_tr = np.where(~s_ho & ~s_in)[0]
    s_iv = np.where(s_in)[0]
    s_te = np.where(s_ho)[0]
    s_idx = np.array([m["idx"] for m in sm])
    s_y = np.array([m["wr"] for m in sm], dtype=np.float32)

    W = leaf["windows"]
    if args.build:
        w_test: list[int] = []
        w_pool = [w["wi"] for w in W]
    else:
        w_test = [w["wi"] for w in W if w["fold"] == args.fold]
        w_pool = [w["wi"] for w in W if w["fold"] != args.fold]
    w_iv = [wi for wi in w_pool if W[wi]["inner"]]
    w_tr = [wi for wi in w_pool if not W[wi]["inner"]]
    leaves_of: dict[int, list[int]] = defaultdict(list)
    for i, m in enumerate(leaf["meta"]):
        leaves_of[m["wi"]].append(i)

    om = outcome["meta"]
    o_held = np.array([m["held"] for m in om])
    o_tr = np.where(~o_held)[0]
    o_te = np.where(o_held)[0]
    if args.smoke:
        s_tr, w_tr, o_tr = s_tr[:400], w_tr[:20], o_tr[:400]
        w_iv, w_test, o_te = w_iv[:10], w_test[:20], o_te[:200]
    print(
        f"[fit {tag}] state train {len(s_tr)} inner {len(s_iv)} holdout {len(s_te)} | "
        f"leaf windows train {len(w_tr)} inner {len(w_iv)} test {len(w_test)} | "
        f"outcome train {len(o_tr)} held {len(o_te)}",
        flush=True,
    )

    # ---- nets
    net, ck = load_net(device)
    teacher, _ = load_net(device)
    teacher.eval()
    for p in teacher.parameters():
        p.requires_grad = False
    n_train_p = set_trainable(net, args.unfreeze)
    opt = torch.optim.AdamW(
        [p for p in net.parameters() if p.requires_grad], lr=args.lr, weight_decay=0.01
    )
    print(f"[fit {tag}] trainable params {n_train_p:,} (unfreeze={args.unfreeze})", flush=True)

    def inner_metrics() -> dict:
        s_rho = (
            spearman(
                scores(net, state["examples"], s_idx[s_iv], device, args.eval_batch), s_y[s_iv]
            )
            if len(s_iv)
            else float("nan")
        )
        cells = oneply_cells(leaf_values(net, leaf, set(w_iv), device, args.eval_batch), W, w_iv)
        c = summarize_cell(cells[HEADLINE])
        one = c.get("spearman_mean")
        return {
            "state_inner": round(s_rho, 4),
            "oneply_inner": one,
            "oneply_inner_n": c.get("n", 0),
        }

    base = inner_metrics()
    print(f"[fit {tag}] day-zero inner: {base}", flush=True)
    best_score, best_state, patience = -9.0, None, 0
    t0 = time.time()
    for epoch in range(1, args.max_epochs + 1):
        net.train()
        # one epoch = every training window once + state/outcome batches shuffled in
        steps = [("leaf", wi) for wi in w_tr]
        perm = rng.permutation(s_tr)
        steps += [
            ("state", perm[i : i + args.batch])
            for i in range(0, len(perm), args.batch)
            if len(perm[i : i + args.batch]) >= 8
        ]
        perm = rng.permutation(o_tr)
        steps += [
            ("out", perm[i : i + args.out_batch])
            for i in range(0, len(perm), args.out_batch)
            if len(perm[i : i + args.out_batch]) >= 8
        ]
        rng.shuffle(steps)
        acc: dict[str, list[float]] = defaultdict(list)
        for kind, sel in steps:
            if kind == "state":
                chunk = _to(collate([state["examples"][j] for j in s_idx[sel]]), device)
                y = torch.tensor(s_y[sel], device=device)
                with torch.autocast(device, dtype=torch.bfloat16):
                    v = value_logits(net, chunk).float()
                rl = rank_loss(v, y, PAIR_GATE_WR, None)
                bce = F.binary_cross_entropy_with_logits(v, y)
                loss = (rl if rl is not None else 0.0) + args.w_state_bce * bce
                acc["state_rank"].append(float(rl) if rl is not None else float("nan"))
                acc["state_bce"].append(float(bce))
            elif kind == "leaf":
                li = leaves_of[sel]
                if len(li) < 4:
                    continue
                if len(li) > args.leaf_cap:
                    li = list(rng.choice(li, args.leaf_cap, replace=False))
                chunk = _to(collate([leaf["examples"][j] for j in li]), device)
                ms = [leaf["meta"][j] for j in li]
                fv = torch.tensor([m["fv"] for m in ms], device=device)
                with torch.autocast(device, dtype=torch.bfloat16):
                    v = value_logits(net, chunk).float()
                distill = F.binary_cross_entropy_with_logits(v, fv)
                # within (roll, hz) groups: rank arms by the paired composite
                groups: dict[tuple, list[int]] = defaultdict(list)
                for k, m in enumerate(ms):
                    if m["arm"] > 0 and m["comp"] is not None:
                        groups[(m["roll"], m["hz"])].append(k)
                rls, ws = [], []
                for ks in groups.values():
                    if len(ks) < 2:
                        continue
                    ks_t = torch.tensor(ks, device=device)
                    rl = rank_loss(
                        v[ks_t],
                        torch.tensor(
                            [ms[k]["comp"] for k in ks], device=device, dtype=torch.float32
                        ),
                        PAIR_GATE_COMP,
                        COMP_SCALE,
                    )
                    if rl is not None:
                        rls.append(rl)
                        ws.append(len(ks))
                rank = sum(r * w for r, w in zip(rls, ws)) / sum(ws) if rls else None
                loss = args.w_leaf_fv * distill + (
                    args.w_leaf_rank * rank if rank is not None else 0.0
                )
                acc["leaf_distill"].append(float(distill))
                if rank is not None:
                    acc["leaf_rank"].append(float(rank))
            else:
                chunk = _to(collate([outcome["examples"][j] for j in sel]), device)
                with torch.autocast(device, dtype=torch.bfloat16):
                    so = net(chunk)
                    with torch.no_grad():
                        tl = teacher(chunk)["policy_logits"].float()
                sl = so["policy_logits"].float()
                lp_s, lp_t = F.log_softmax(sl, -1), F.log_softmax(tl, -1)
                kl = (lp_t.exp() * (lp_t - lp_s)).masked_fill(~chunk["cand_mask"], 0).sum(-1).mean()
                vb = F.binary_cross_entropy_with_logits(
                    so["value_logit"].float(), chunk["won"].float()
                )
                loss = args.w_outcome * vb + args.w_kl * kl
                acc["out_bce"].append(float(vb))
                acc["out_kl"].append(float(kl))
            opt.zero_grad(set_to_none=True)
            loss.backward()
            if args.clip:
                torch.nn.utils.clip_grad_norm_(
                    [p for p in net.parameters() if p.requires_grad], args.clip
                )
            opt.step()
        im = inner_metrics()
        s_in = im["state_inner"] if im["state_inner"] == im["state_inner"] else 0.0
        score = s_in if args.stop == "state" else s_in + (im["oneply_inner"] or 0.0)

        row = {
            "epoch": epoch,
            "steps": len(steps),
            "wall_min": round((time.time() - t0) / 60, 1),
            **{k: round(float(np.nanmean(v)), 4) for k, v in acc.items()},
            **im,
            "score": round(score, 4),
        }
        log.write(json.dumps(row) + "\n")
        log.flush()
        print(f"[fit {tag}] {row}", flush=True)
        if score > best_score:
            best_score, patience = score, 0
            best_state = {k: v.detach().clone().cpu() for k, v in net.state_dict().items()}
        else:
            patience += 1
            if patience >= args.patience:
                break
    if best_state is not None:
        net.load_state_dict(best_state)

    # ---- reads on the restored best
    res = {
        "tag": tag,
        "fold": None if args.build else args.fold,
        "unfreeze": args.unfreeze,
        "lr": args.lr,
        "stop": args.stop,
        "trainable_params": n_train_p,
        "epochs": epoch,
        "best_inner_score": round(best_score, 4),
        "day_zero_inner": base,
        "wall_min": round((time.time() - t0) / 60, 1),
    }
    res["state_holdout_spearman"] = round(
        spearman(scores(net, state["examples"], s_idx[s_te], device, args.eval_batch), s_y[s_te]), 4
    )
    res["state_holdout_n"] = int(len(s_te))
    if w_test:
        cells = oneply_cells(
            leaf_values(net, leaf, set(w_test), device, args.eval_batch), W, w_test
        )
        res["oneply_test"] = {k: summarize_cell(c) for k, c in cells.items()}
        res["oneply_test_rhos"] = {k: c["rhos"] for k, c in cells.items()}
        res["oneply_test_top1"] = {k: c["top1"] for k, c in cells.items()}
    res["drift_held"] = drift_read(net, teacher, outcome, o_te, device, args.eval_batch)
    (out_dir / f"result-{tag}.json").write_text(json.dumps(res, indent=1) + "\n")
    print(
        f"[fit {tag}] state holdout {res['state_holdout_spearman']} | one-ply test {res.get('oneply_test', {}).get(HEADLINE)} | drift {res['drift_held']}",
        flush=True,
    )

    if args.build:
        ck_out = REPO / args.ckpt_out
        ck_out.mkdir(parents=True, exist_ok=True)
        config = {
            **ck["config"],
            "value_pretrain": {
                "mode": "m12-build1",
                "base_ckpt": CKPT,
                "base_step": ck.get("step"),
                "unfreeze": args.unfreeze,
                "lr": args.lr,
                "families": {"state": LABELSET, "leaf": CL2_READ, "outcome": list(OUTCOME_STORES)},
                "weights": {
                    "state_bce": args.w_state_bce,
                    "leaf_fv": args.w_leaf_fv,
                    "leaf_rank": args.w_leaf_rank,
                    "outcome": args.w_outcome,
                    "kl": args.w_kl,
                },
                "state_holdout_spearman": res["state_holdout_spearman"],
                "drift_held": res["drift_held"],
                "created": _dt.date.today().isoformat(),
                "note": "day-zero POLICY checkpoint — policy heads kept by a KL anchor to iter-019; the masked value head is the Build 1 asset",
            },
        }
        torch.save(
            {"step": ck.get("step"), "model": net.state_dict(), "config": config},
            ck_out / "last.pt",
        )
        print(f"[fit build] -> {ck_out}/last.pt", flush=True)


# ------------------------------------------------------------- read


def read(args: argparse.Namespace) -> None:
    out_dir = REPO / args.out
    folds = sorted(out_dir.glob("result-fold*.json"))
    build = out_dir / "result-build.json"
    pooled: dict[str, dict] = defaultdict(
        lambda: {"rhos": [], "top1": [], "n_lt3": 0, "n_const": 0}
    )
    per_fold = []
    for f in folds:
        r = json.loads(f.read_text())
        per_fold.append(
            {
                "fold": r["fold"],
                "state_holdout": r["state_holdout_spearman"],
                "oneply": r["oneply_test"][HEADLINE].get("spearman_mean"),
                "epochs": r["epochs"],
                "drift": r["drift_held"],
            }
        )
        for k, rhos in r["oneply_test_rhos"].items():
            pooled[k]["rhos"] += rhos
            pooled[k]["top1"] += r["oneply_test_top1"][k]
            pooled[k]["n_lt3"] += r["oneply_test"][k].get("n_lt3", 0)
            pooled[k]["n_const"] += r["oneply_test"][k].get("n_const", 0)
    cells = {k: summarize_cell(c) for k, c in pooled.items()}
    one = cells.get(HEADLINE, {}).get("spearman_mean")
    state_ho = None
    drift = None
    if build.exists():
        b = json.loads(build.read_text())
        state_ho, drift = b["state_holdout_spearman"], b["drift_held"]
    elif per_fold:
        state_ho = round(sum(x["state_holdout"] for x in per_fold) / len(per_fold), 4)
    go = (one is not None and one >= BARS["oneply_go"]) or (
        state_ho is not None and state_ho >= BARS["state_go"]
    )
    kill = (one is None or one < BARS["kill"]) and (state_ho is None or state_ho < BARS["kill"])
    verdict = "GO" if go else ("KILL" if kill else "IN-BAND")
    res = {
        "bars": BARS,
        "verdict": verdict,
        "oneply_crossfit": cells,
        "state_holdout_spearman": state_ho,
        "drift_held": drift,
        "folds": per_fold,
        "reference": {"oneply_masked_eot_k1": 0.277, "state_ranking_prior": "0.27-0.48"},
    }
    (out_dir / "build1-read.json").write_text(json.dumps(res, indent=1) + "\n")
    lines = [
        f"# M12 Build 1 read — {out_dir.name}",
        "",
        f"**Verdict: {verdict}** (GO one-ply ≥ {BARS['oneply_go']} and/or state-ranking ≥ {BARS['state_go']}; KILL if neither clears {BARS['kill']})",
        "",
        f"- one-ply masked/eot/K=1 vs comp8, cross-fit over {len(folds)} folds: **{one}** ± {cells.get(HEADLINE, {}).get('spearman_se')} (n {cells.get(HEADLINE, {}).get('n')}; reference 0.277 ± 0.022)",
        f"- state-ranking frozen-holdout Spearman: **{state_ho}** (reference 0.27–0.48; rank-critic-c2v3 standalone 0.483)",
        f"- policy drift on held-out windows: {drift}",
        "",
        "| cell | n | Spearman mean ± se | median | top-1 |",
        "|---|---|---|---|---|",
    ]
    for k, c in cells.items():
        lines.append(
            f"| {k} | {c.get('n')} | {c.get('spearman_mean')} ± {c.get('spearman_se')} | {c.get('spearman_median')} | {c.get('top1')} |"
        )
    lines += [
        "",
        "| fold | state holdout | one-ply test | epochs | KL mean | argmax agree |",
        "|---|---|---|---|---|---|",
    ]
    for x in per_fold:
        lines.append(
            f"| {x['fold']} | {x['state_holdout']} | {x['oneply']} | {x['epochs']} | {x['drift']['kl_mean']} | {x['drift']['argmax_agree']} |"
        )
    (out_dir / "build1-read.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


# ------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("bank")
    p.add_argument("--out", required=True)
    p.add_argument("--families", default="state,leaf,outcome")
    p.add_argument("--outcome-per-store", type=int, default=24000)
    p.add_argument("--outcome-keep", type=float, default=1 / 6)
    p.add_argument("--seed", type=int, default=20260906)
    p.add_argument("--smoke", type=int, default=None, help="cap rows/windows per family")
    p.set_defaults(fn=bank)
    p = sub.add_parser("fit")
    p.add_argument("--out", required=True)
    p.add_argument("--fold", type=int, default=None)
    p.add_argument(
        "--build", action="store_true", help="train on every window; save the day-zero ckpt"
    )
    p.add_argument("--ckpt-out", default="data/training/m12-build1")
    p.add_argument("--unfreeze", default="4", help="top-N trunk layers, or 'all'")
    p.add_argument("--lr", type=float, default=3e-5)
    p.add_argument("--batch", type=int, default=192)
    p.add_argument("--out-batch", type=int, default=96)
    p.add_argument("--leaf-cap", type=int, default=288)
    p.add_argument("--eval-batch", type=int, default=256)
    p.add_argument("--max-epochs", type=int, default=30)
    p.add_argument("--patience", type=int, default=5)
    p.add_argument(
        "--stop",
        default="both",
        choices=("both", "state"),
        help="early-stop signal: state inner-val + inner one-ply (default) or state inner-val only",
    )
    p.add_argument("--clip", type=float, default=1.0)
    p.add_argument("--w-state-bce", type=float, default=0.05)
    p.add_argument("--w-leaf-fv", type=float, default=1.0)
    p.add_argument("--w-leaf-rank", type=float, default=1.0)
    p.add_argument("--w-outcome", type=float, default=0.5)
    p.add_argument("--w-kl", type=float, default=2.0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--smoke", action="store_true")
    p.set_defaults(fn=fit)
    p = sub.add_parser("read")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=read)
    args = ap.parse_args()
    if args.cmd == "fit" and not args.build and args.fold is None:
        ap.error("fit needs --fold K or --build")
    args.fn(args)


if __name__ == "__main__":
    main()
