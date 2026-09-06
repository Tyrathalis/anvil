#!/usr/bin/env python3
"""M11 Build 1 — the OPTION SCORER fit (m11-plan.md build 1; the KILL lives
here). Fit the scorer head (model.score_options: q([STATE]) · pool(arm keys))
on a TRAINABLE copy of the trunk, on the certifier's per-option spreads
(harvest h1 + mint 20260830: ~3,475 windows × ~14 arms), and read within-
window Spearman vs the search's ranking on game-hash holdout — against the
FROZEN-trunk probe (sched_scorer_probe.py: 0.08 flat at N=607).

PRE-REGISTERED (2026-09-06, user-adjudicated):
  at N = 607 train windows (the probe's N):  Spearman <= 0.15 -> KILL
                                              Spearman >  0.30 -> PASS (done-when 2)
  in between: the 25/50/100% curve on all windows decides — rising AND
  > 0.30 at full N passes, otherwise KILL.  Pivotality AUC >= 0.70 read alongside.
Recipe: init = m10-sched-init (the ckpt of record's trunk + fresh sched
params) with the option keys copied from the executor's own pointer
(sched_key <- ptr_key, sched_sa_proj <- sa_proj, opt_query <- ptr_query);
full fine-tune (trunk lr 1e-5, heads 1e-3, AdamW) vs a FROZEN-trunk twin on
the same head/data/recipe; loss = within-window pairwise ranking (softplus
hinge on sign, |Δy| > 0.5) + 0.05 · MSE scale anchor; target = the arm's
8-roll composite mean (select + score halves); early stop on holdout
Spearman. Deterministic forward (eval-mode norm/dropout) in both modes.

Usage:
  uv run python scripts/option_scorer_fit.py build --out data/training/m11-scorer-b1
  uv run python scripts/option_scorer_fit.py fit --out data/training/m11-scorer-b1 \
      [--modes full,frozen --fracs 607,0.25,0.5,1.0 --seeds 3]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sched_pins as pins  # noqa: E402
from sched_certify_finish import _emission_window, load_arms  # noqa: E402
from schedule_read import arm_scores, certify_turn, load_rows, read_sched  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
HARVEST = REPO / "data/runs/sched-harvest-h1/harvest-manifest.json"
MINT = REPO / "data/runs/sched-mint-20260830"
CKPT_INIT = REPO / "data/training/m10-sched-init/last.pt"
BANDS = {"kill_at_607": 0.15, "pass": 0.30, "pivotality_auc": 0.70, "probe_n": 607}
HOLD_FRAC = 0.25


HOLD_SALT = {"v": ""}  # --hold-salt: a different game-hash holdout (small corpora read 3 splits)


def hold(key) -> bool:
    """game-hash holdout on (store, g) — the probe's split, so the read is comparable."""
    k = tuple(key) if key[0] == "pay" else tuple(key[:2])  # pay windows are one census game each
    h = hashlib.blake2b((repr(k) + HOLD_SALT["v"]).encode(), digest_size=8).digest()
    return int.from_bytes(h, "big") / 2**64 < HOLD_FRAC


def spearman(a, b) -> float:
    n = len(a)
    if n < 3:
        return float("nan")
    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else float("nan")


def auc(scores, y) -> float:
    pos = [s for s, t in zip(scores, y) if t]
    neg = [s for s, t in zip(scores, y) if not t]
    if not pos or not neg:
        return float("nan")
    return sum((1.0 if a > b else 0.5 if a == b else 0.0) for a in pos for b in neg) / (len(pos) * len(neg))


# ---------------------------------------------------------------- build

def _sources() -> list[dict]:
    """(store, spread rows by (g,t), arm defs by (g,t)) per source."""
    out = []
    m = json.loads(HARVEST.read_text())
    for b in m["batches"]:
        spreads = {}
        for ln in open(b["labels"].replace(".jsonl", ".spread.jsonl")):
            s = json.loads(ln)
            spreads[(s["g"], s["t"])] = s
        arms = load_arms([str(Path(b["run"]) / "workers" / "inv-*" / "labels.jsonl")])
        out.append({"tag": "harvest", "store": b["store"], "spreads": spreads, "arms": arms})
    for sdir in sorted(MINT.glob("store-*")):
        run_id = sdir.name[len("store-"):]
        sched = read_sched(str(sdir / "sched-h2.tsv"))
        rows = load_rows([str(sdir / "lanes" / "lane-*.out.jsonl")])
        spreads, arms = {}, {}
        for key, plan in sched.items():
            entry = rows.get(key)
            if entry is None or entry["skips"] or not entry["nat"]:
                continue
            seat = plan["seat"]
            srows = []
            for arm_id, arows in sorted(entry["arms"].items()):
                sel = arm_scores(arows, entry["nat"], seat, pins.SELECT_ROLLS)
                sco = arm_scores(arows, entry["nat"], seat, pins.SCORE_ROLLS)
                if any(r.get("void") for r in arows.values()):
                    continue
                srows.append({"arm": arm_id, "n_sel": len(sel), "n_sco": len(sco),
                              "select_mean": sum(sel) / len(sel) if sel else None,
                              "score_mean": sum(sco) / len(sco) if sco else None})
            cert = certify_turn(entry, seat)
            spreads[key] = {"g": key[0], "t": key[1], "seat": seat, "arms": srows,
                            "certified": bool(cert.get("certified"))}
            arms[key] = {"seat": seat, "arms": {a: (m_, list(labels)) for a, (m_, labels) in plan["arms"].items()}}
        out.append({"tag": "mint", "store": str(REPO / "data/trajectories" / run_id), "spreads": spreads, "arms": arms})
    return out


@torch.no_grad()
def build(args) -> None:
    from anvil.bridge.featurize import Featurizer, store_wire_hist
    from anvil.store.trajectories import TrajectoryStore
    from anvil.training.dataset import default_methods

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ck = torch.load(CKPT_INIT, map_location="cpu", weights_only=False)
    cfg = ck["config"]
    feat = Featurizer(cfg["embed"], default_methods(), ability_table=str(REPO / "data/pool/ability-table.json"))
    stats: Counter = Counter()
    windows = []
    t0 = time.time()
    for src in _sources():
        st = TrajectoryStore(Path(src["store"]))
        sname = Path(src["store"]).name
        by_game = defaultdict(list)
        for key, s in src["spreads"].items():
            by_game[key[0]].append(s)
        for g, sps in sorted(by_game.items()):
            try:
                traj = st.game(g)
            except Exception:  # noqa: BLE001
                stats[f"{src['tag']}_undecodable"] += 1
                continue
            decs = traj.decisions
            for s in sps:
                win = _emission_window(decs, s["seat"], s["t"])
                if win is None:
                    stats[f"{src['tag']}_no_emission_window"] += 1
                    continue
                emis_i, dec = win
                wire = dict(dec)
                if "hist" not in dec:
                    wire["hist"] = store_wire_hist(decs[:emis_i], dec.get("_pos", emis_i))
                try:
                    ex, aux = feat.example(wire, traj.header, "priority")
                except Exception as e:  # noqa: BLE001
                    stats[f"{src['tag']}_featurize_{type(e).__name__}"] += 1
                    continue
                opts = dec.get("opts") or []
                cand_of = {}
                for j, fo in enumerate(aux["cand_first_opt"]):
                    if j == 0 or fo < 0:
                        continue
                    cand_of.setdefault(str(opts[fo].get("sa") or "")[:60], j)
                defs = src["arms"].get((s["g"], s["t"]), {}).get("arms", {})
                arms = []
                for a in s["arms"]:
                    if a["score_mean"] is None or a["select_mean"] is None:
                        continue
                    labels = defs.get(a["arm"], ("", []))[1]
                    idxs = [cand_of.get(lab[:60]) for lab in labels]
                    if any(i is None for i in idxs):
                        stats[f"{src['tag']}_arm_unmapped"] += 1
                        continue
                    target = (a["n_sel"] * a["select_mean"] + a["n_sco"] * a["score_mean"]) / max(1, a["n_sel"] + a["n_sco"])
                    arms.append({"arm": a["arm"], "idxs": idxs, "target": float(target),
                                 "score_mean": float(a["score_mean"])})
                if len(arms) < 3:
                    stats[f"{src['tag']}_lt3_arms"] += 1
                    continue
                ex = {k: v for k, v in ex.items() if torch.is_tensor(v) and not k.startswith("sched_cand_")}
                windows.append({"key": (sname, s["g"], s["t"]), "src": src["tag"], "seat": s["seat"],
                                "ex": ex, "arms": arms, "certified": bool(s["certified"])})
                stats[f"{src['tag']}_windows"] += 1
            del traj
        print(f"[build] {sname}: {stats} ({time.time() - t0:.0f}s)", flush=True)
    torch.save({"windows": windows, "stats": dict(stats), "ckpt_init": str(CKPT_INIT)}, out / "windows.pt")
    n_arms = sum(len(w["arms"]) for w in windows)
    print(f"[build] {len(windows)} windows, {n_arms} (window, arm) pairs -> {out / 'windows.pt'}; "
          f"holdout {sum(hold(w['key']) for w in windows)}")


# ---------------------------------------------------------------- build-pay (R2, ADR-0099)

PAY_OBSERVE = REPO / "data/census/run-20260828-revalidation-cousins"
PAY_CERTOUT = {"b1": "data/census/run-20260820-paygoals3/certify.out.jsonl",
               "b2": "data/census/run-20260820-paygoals3/certify2.out.jsonl",
               "b3": "data/census/run-20260820-paygoals3/certify3.out.jsonl",
               "b4": "data/census/run-20260821-handbuilt/certify4.out.jsonl"}


@torch.no_grad()
def build_pay(args) -> None:
    """The SINGLE-OPTION surface: ADR-0075/0082 payment-class drills as
    per-option spreads. Options = the observe frame's goal options (index 0 =
    auto = the natural line, score 0); target per option = the shape-score
    margin over arm 0, paired by roll (payment_certify._score verbatim), mean
    over faithfully-executed rolls. Windows = the 293 observed drills
    (evalset v2 positives + auto-correct + the 13 retired phyrexian
    positives, flagged); the ratesweep holdout has no observe frames yet."""
    import sys as _sys
    _sys.path.insert(0, str(REPO / "scripts"))
    from payment_certify import _axes, _score
    from payment_drill_score import _observe_frames

    from anvil.bridge.featurize import Featurizer
    from anvil.training.dataset import default_methods

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ck = torch.load(CKPT_INIT, map_location="cpu", weights_only=False)
    feat = Featurizer(ck["config"]["embed"], default_methods())
    rows: dict = defaultdict(lambda: defaultdict(list))
    for b, path in PAY_CERTOUT.items():
        for ln in open(REPO / path):
            r = json.loads(ln)
            if r.get("ev") == "certify":
                rows[b][(r["job"], r["arm"])].append(r)
    frames = _observe_frames(sorted(str(p) for p in PAY_OBSERVE.glob("observe-lane-*.obs.zst")))
    stats: Counter = Counter()
    windows = []
    for j in map(json.loads, open(PAY_OBSERVE / "observe-jobs.jsonl")):
        f = frames.get(j["job"])
        if f is None:
            stats["no_frame"] += 1
            continue
        header, w = f
        if len(w["opts"]) != j["exp_options"] + 1:
            stats["option_mismatch"] += 1
            continue
        seat = 0 if j["deck1"].removesuffix(".dck") in j["p"] else 1
        base = sorted(rows[j["batch"]].get((j["orig_job"], 0), []), key=lambda x: x["roll"])
        if not base:
            stats["no_baseline"] += 1
            continue
        arms = [{"arm": 0, "idxs": [0], "target": 0.0}]
        for a in range(1, j["exp_options"] + 1):
            arows = sorted(rows[j["batch"]].get((j["orig_job"], a), []), key=lambda x: x["roll"])
            paired = [_score(j["shape"], _axes(r, seat), _axes(bb, seat))
                      for r, bb in zip(arows, base) if r["fired"] and r.get("exec") == "directed_ok"]
            if not paired:
                stats["arm_unexecuted"] += 1
                continue
            arms.append({"arm": a, "idxs": [a], "target": float(sum(paired) / len(paired))})
        if len(arms) < 3:
            stats["lt3_options"] += 1
            continue
        try:
            ex, _aux = feat.example(w, header, "pay_class")
        except Exception as e:  # noqa: BLE001
            stats[f"featurize_{type(e).__name__}"] += 1
            continue
        if max(a["arm"] for a in arms) >= ex["cand_rows"].shape[0]:
            stats["cand_short"] += 1
            continue
        ex = {k: v for k, v in ex.items() if torch.is_tensor(v)}
        windows.append({"key": ("pay", j["batch"], j["orig_job"]), "src": j["shape"], "seat": seat,
                        "ex": ex, "arms": arms, "certified": j["kind"] == "positive",
                        "retired": j["batch"] == "b1" and j["shape"] == "phyrexian"})
        stats["windows"] += 1
    torch.save({"windows": windows, "stats": dict(stats), "ckpt_init": str(CKPT_INIT), "surface": "pay"}, out / "windows.pt")
    print(f"[build-pay] {stats} -> {len(windows)} windows, {sum(len(w['arms']) for w in windows)} options; "
          f"holdout {sum(hold(w['key']) for w in windows)}; certified {sum(w['certified'] for w in windows)}")


# ---------------------------------------------------------------- fit

def _net(dev):
    from anvil.training.dataset import default_methods
    from anvil.training.train import build_net
    ck = torch.load(CKPT_INIT, map_location=dev, weights_only=False)
    cfg = ck["config"]
    net = build_net(cfg["embed"], cfg["pool_manifest"], len(default_methods()),
                    n_sa=cfg.get("sa_vocab_size", 0)).to(dev)
    net.load_compat(ck["model"])
    with torch.no_grad():
        # option keys = the executor's own pointer keys; the scorer query =
        # its pointer query (the scorer starts as "the executor's own
        # preference pooled over the arm")
        net.sched_key.weight.copy_(net.ptr_key.weight)
        net.sched_key.bias.copy_(net.ptr_key.bias)
        net.sched_sa_proj.weight.copy_(net.sa_proj.weight)
        net.sched_sa_proj.bias.copy_(net.sa_proj.bias)
        net.opt_query.weight.copy_(net.ptr_query.weight)
        net.opt_query.bias.copy_(net.ptr_query.bias)
    net.eval()  # deterministic forward in both modes (no dropout on a 2.6K-window fit)
    return net, cfg


SURFACE = {"mode": "sched"}  # "sched" = plan-type options (score_options); "pay" = the pointer logits
HEAD_NAMES = {"sched": ("opt_", "sched_key", "sched_sa_proj"),
              "pay": ("ptr_", "pay_", "pass_head", "sa_proj")}


def _scores(net, batch_windows, dev):
    from anvil.training.dataset import collate
    bt = collate([w["ex"] for w in batch_windows])
    bt = {k: (v.to(dev) if torch.is_tensor(v) else v) for k, v in bt.items()}
    card_vecs = net.cards(bt["ent_emb"])
    tokens, pad = net.assemble(card_vecs, bt)
    out = net.trunk(tokens, src_key_padding_mask=pad)
    state = out[:, 0]
    n_ent = bt["entities"].shape[1]
    ent_out = out[:, 2:2 + n_ent]
    if SURFACE["mode"] == "pay":
        # single-option surface: the pointer logits ARE the scores; option 0
        # (auto = the natural line) anchors at 0 (advantage semantics)
        logits = net._pointer_logits(state, ent_out, bt)
        return [logits[b, [a["arm"] for a in w["arms"]]] - logits[b, 0]
                for b, w in enumerate(batch_windows)]
    keys, _vecs, _mask = net._sched_keys(ent_out, bt)
    return net.score_options(state, keys, [[a["idxs"] for a in w["arms"]] for w in batch_windows])


def _loss(p: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    diff_p = p.unsqueeze(0) - p.unsqueeze(1)
    diff_y = y.unsqueeze(0) - y.unsqueeze(1)
    m = (diff_y.abs() > 0.5).float()
    pair = torch.nn.functional.softplus(-diff_p * torch.sign(diff_y)) * m
    return pair.sum() / m.sum().clamp(min=1.0) + 0.05 * ((p - y) ** 2).mean()


@torch.no_grad()
def evaluate(net, windows, dev, bs=8) -> dict:
    rhos, top1, piv_s, piv_y, by_src, by_cert = [], 0, [], [], defaultdict(list), defaultdict(list)
    for i in range(0, len(windows), bs):
        chunk = windows[i:i + bs]
        for w, p in zip(chunk, _scores(net, chunk, dev)):
            p = p.float().cpu().tolist()
            y = [a["target"] for a in w["arms"]]
            rho = spearman(p, y)
            if rho != rho:
                continue
            rhos.append(rho)
            if "spread" in w["arms"][0]:
                r2 = spearman(p, [a["spread"] for a in w["arms"]])
                if r2 == r2:
                    by_src["vs_spread"].append(r2)
            by_src[w["src"]].append(rho)
            by_cert[w["certified"]].append(rho)
            top1 += int(max(range(len(p)), key=lambda k: p[k]) == max(range(len(y)), key=lambda k: y[k]))
            piv_s.append(max(p))
            piv_y.append(int(w["certified"]))
    n = len(rhos)
    return {"n": n, "spearman": round(sum(rhos) / n, 4) if n else None,
            "spearman_se": round((sum((x - sum(rhos) / n) ** 2 for x in rhos) / max(1, n - 1)) ** 0.5 / n ** 0.5, 4) if n > 1 else None,
            "top1": round(top1 / n, 3) if n else None,
            "pivotality_auc": round(auc(piv_s, piv_y), 3) if n else None,
            "by_src": {k: round(sum(v) / len(v), 3) for k, v in by_src.items()},
            "by_certified": {str(k): round(sum(v) / len(v), 3) for k, v in by_cert.items()}}


def fit_one(train, test, mode: str, seed: int, dev, args, save_to: Path | None = None) -> dict:
    torch.manual_seed(seed)
    rng = random.Random(seed)
    net, _cfg = _net(dev)
    head_names = HEAD_NAMES[SURFACE["mode"]]
    head, trunk = [], []
    for name, p in net.named_parameters():
        if name.startswith(head_names):
            head.append(p)
        elif mode == "full":
            trunk.append(p)
        else:
            p.requires_grad_(False)
    groups = [{"params": head, "lr": args.lr_head}]
    if trunk:
        groups.append({"params": trunk, "lr": args.lr_trunk})
    opt = torch.optim.AdamW(groups, weight_decay=0.01)
    best, best_state, bad = None, None, 0
    hist = []
    t0 = time.time()
    for ep in range(args.epochs):
        rng.shuffle(train)
        tot, nb = 0.0, 0
        for i in range(0, len(train), args.batch):
            chunk = train[i:i + args.batch]
            ps = _scores(net, chunk, dev)
            loss = sum(_loss(p, torch.tensor([a["target"] for a in w["arms"]], device=dev))
                       for w, p in zip(chunk, ps)) / len(chunk)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for g in groups for p in g["params"]], 1.0)
            opt.step()
            tot += float(loss)
            nb += 1
        ev = evaluate(net, test, dev)
        hist.append({"epoch": ep, "train_loss": round(tot / max(1, nb), 4), **{k: ev[k] for k in ("spearman", "top1", "pivotality_auc")}})
        print(f"  [{mode} s{seed} n{len(train)}] ep{ep} loss {tot / max(1, nb):.4f} holdout {ev['spearman']} top1 {ev['top1']} auc {ev['pivotality_auc']} ({time.time() - t0:.0f}s)", flush=True)
        if best is None or ev["spearman"] > best["spearman"]:
            best, bad = ev, 0
            if save_to:
                best_state = {k: v.detach().cpu() for k, v in net.state_dict().items()}
        else:
            bad += 1
            if bad >= args.patience:
                break
    if save_to and best_state is not None:
        ck = torch.load(CKPT_INIT, map_location="cpu", weights_only=False)
        torch.save({"model": best_state, "config": ck["config"], "step": ck.get("step"),
                    "scorer_fit": {"mode": mode, "seed": seed, "n_train": len(train), "best": best}}, save_to)
    return {"mode": mode, "seed": seed, "n_train": len(train), "best": best, "epochs_run": len(hist), "hist": hist}


def _apply_targets(windows: list[dict], path: str, col: str) -> list[dict]:
    """R1 (ADR-0099): swap the fit target for an alternate per-arm label (the
    critic's one-step Δ from a lookahead read); the spread target survives as
    a["spread"] so evaluate() reads both. Windows/arms without the alternate
    label are dropped."""
    tg = json.load(open(path))
    kept = []
    for w in windows:
        rec = tg.get("|".join(map(str, w["key"])))
        if not rec:
            continue
        arms = []
        for a in w["arms"]:
            v = rec.get(str(a["arm"]), {}).get(col)
            if v is None:
                continue
            arms.append({**a, "spread": a["target"], "target": float(v)})
        if len(arms) >= 3:
            kept.append({**w, "arms": arms})
    print(f"[fit] alternate targets {col}: {len(kept)}/{len(windows)} windows kept")
    return kept


def fit(args) -> None:
    out = Path(args.out)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    data = torch.load(args.windows or (out / "windows.pt"), weights_only=False)
    windows = data["windows"]
    SURFACE["mode"] = data.get("surface", "sched")
    HOLD_SALT["v"] = args.hold_salt
    print(f"[fit] surface {SURFACE['mode']}")
    if args.targets:
        windows = _apply_targets(windows, args.targets, args.target_col)
        out.mkdir(parents=True, exist_ok=True)
    test = [w for w in windows if hold(w["key"])]
    train_all = [w for w in windows if not hold(w["key"])]
    print(f"[fit] {len(train_all)} train / {len(test)} holdout windows; "
          f"src {dict(Counter(w['src'] for w in windows))}; certified {sum(w['certified'] for w in windows)}")
    modes = args.modes.split(",")
    fracs = [float(x) for x in args.fracs.split(",")]
    results = []
    res_path = out / "curve.json"
    for frac in fracs:
        n = int(frac) if frac > 1 else int(len(train_all) * frac)
        for mode in modes:
            for seed in range(args.seeds):
                rng = random.Random(1000 + seed)
                sub = list(train_all)
                rng.shuffle(sub)
                sub = sub[:n]
                save = out / f"best-{mode}.pt" if (frac == 1.0 and seed == 0) else None
                r = fit_one(sub, test, mode, seed, dev, args, save_to=save)
                r["frac"] = frac
                results.append(r)
                json.dump({"bands": BANDS, "n_test": len(test), "results": results}, open(res_path, "w"), indent=1)
                print(f"[fit] frac {frac} n {n} {mode} seed {seed}: best {r['best']}", flush=True)
    report(out)


def report(out: Path) -> None:
    d = json.load(open(out / "curve.json"))
    agg = defaultdict(list)
    for r in d["results"]:
        agg[(r["frac"], r["mode"])].append(r)
    lines = ["# Option scorer fit — " + out.name, "", f"holdout windows {d['n_test']}; bands {d['bands']}", "",
             "| n_train | mode | seeds | Spearman mean (per-seed) | top-1 | pivotality AUC | by src | by certified |", "|---|---|---|---|---|---|---|---|"]
    at607 = {}
    full = {}
    for (frac, mode), rs in sorted(agg.items()):
        sp = [r["best"]["spearman"] for r in rs]
        mean = sum(sp) / len(sp)
        lines.append(f"| {rs[0]['n_train']} | {mode} | {len(rs)} | {mean:.3f} ({', '.join(f'{x:.3f}' for x in sp)}) | "
                     f"{sum(r['best']['top1'] for r in rs) / len(rs):.3f} | {sum(r['best']['pivotality_auc'] for r in rs) / len(rs):.3f} | "
                     f"{rs[0]['best']['by_src']} | {rs[0]['best']['by_certified']} |")
        if rs[0]["n_train"] == BANDS["probe_n"]:
            at607[mode] = mean
        if frac == 1.0:
            full[mode] = mean
    verdict = None
    if "full" in at607:
        v = at607["full"]
        if v <= BANDS["kill_at_607"]:
            verdict = f"KILL (full-trunk scorer {v:.3f} <= {BANDS['kill_at_607']} at N=607)"
        elif v > BANDS["pass"]:
            verdict = f"PASS at N=607 ({v:.3f} > {BANDS['pass']})"
        elif "full" in full:
            rising = full["full"] > v
            verdict = (f"PASS by the curve (607: {v:.3f}; full N: {full['full']:.3f}, rising)"
                       if rising and full["full"] > BANDS["pass"]
                       else f"KILL by the curve (607: {v:.3f}; full N: {full['full']:.3f}, rising={rising})")
        else:
            verdict = f"BETWEEN at N=607 ({v:.3f}); the full-N curve decides"
    lines += ["", f"**Verdict: {verdict}**", "", "frozen probe reference: 0.08 flat at N=607; label ceiling 0.66; one-turn critic 0.30 (ADR-0098)."]
    (out / "read.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", required=True)
    bp = sub.add_parser("build-pay")
    bp.add_argument("--out", required=True)
    f = sub.add_parser("fit")
    f.add_argument("--out", required=True)
    f.add_argument("--modes", default="full,frozen")
    f.add_argument("--fracs", default="607,0.25,0.5,1.0")
    f.add_argument("--seeds", type=int, default=3)
    f.add_argument("--epochs", type=int, default=20)
    f.add_argument("--patience", type=int, default=4)
    f.add_argument("--batch", type=int, default=8)
    f.add_argument("--lr-head", type=float, default=1e-3)
    f.add_argument("--lr-trunk", type=float, default=1e-5)
    f.add_argument("--windows", default=None, help="alternate windows.pt (default <out>/windows.pt)")
    f.add_argument("--targets", default=None, help="alternate per-arm targets json (R1: critic lookahead)")
    f.add_argument("--target-col", default="fv_eot_k1")
    f.add_argument("--hold-salt", default="")
    r = sub.add_parser("report")
    r.add_argument("--out", required=True)
    a = ap.parse_args()
    {"build": build, "build-pay": build_pay, "fit": fit, "report": lambda a: report(Path(a.out))}[a.cmd](a)


if __name__ == "__main__":
    main()
