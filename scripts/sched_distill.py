#!/usr/bin/env python3
"""ADR-0095 route 1: distill the planner on the EXECUTOR'S OWN STRATEGY.

The day-zero read (ADR-0095) found binding damage monotone in the amount of
the plan bound — the mint-distilled planner is worse than the cast head at
every slot. Route 1 (user, 2026-09-03): before any binding regime, fit the
planner head to reproduce the executor's realized turn plans, at scale,
from stores where NO planner influenced play (argmax serve of the ckpt of
record: the M9 rebaseline/control arms, the ADR-0078 ceiling census). A
faithful planner reads ≈ 0 against advisory on the day-zero instrument;
certified labels are then the layer that can add.

Target (m10-build-spec §4 semantics, sched_targets.sched_annotate rules):
per own turn, the emission window = the first own MAIN1 priority window
with obs; the target = the executor's chosen candidates at own priority
windows from the emission window onward this turn, in order, matched to
the emission window's candidate basis by (entity, normalized sa); lands
EXCLUDED (the executor's land-first convention — a plan is ≤6 casts);
unmatched casts (cards not in the emission basis) dropped and counted;
STOP after the last. Empty turns are targets too (the planner must learn
holds where the executor holds).

Head-only fit: only sched_query / sched_key / sched_sa_proj /
sched_stop_key / sched_slot_emb train; the trunk, the cast head, the
shared sa/kind embeddings, the slot-token projection (zero-init: advisory
= the executor exactly) and the E/R heads stay frozen — the executor the
planner must match is untouched, so the paired read isolates the planner.

Usage:
  uv run python scripts/sched_distill.py build --out data/training/m10-planner-distill \
      --stores data/trajectories/m9-rebaselinearm-s0-... [...] [--max-games N]
  uv run python scripts/sched_distill.py fit --out data/training/m10-planner-distill \
      --ckpt data/training/m10-sched-init/last.pt [--epochs 8 --lr 1e-3 --holdout 0.1]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from collections import Counter
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

HEAD_PARAMS = ("sched_query", "sched_key", "sched_sa_proj", "sched_stop_key", "sched_slot_emb")


# ------------------------------------------------------------------ targets

def _chosen_key(dec: dict) -> "tuple | None":
    """(entity, normalized sa, kind) the executor chose at a priority window,
    from the record's option index (exact) or its returned plan (the
    dataset.py prefix rule); None for PASS / unmappable."""
    from anvil.training.dataset import norm_sa

    opts = dec.get("opts") or []
    oi = dec.get("oi")
    if oi is not None and 0 <= oi < len(opts):
        o = opts[oi]
        return o.get("e"), norm_sa(o.get("sa", "")), o.get("kind")
    ret = dec.get("ret")
    plan = ret[0] if isinstance(ret, list) and ret else None
    if not plan or plan.get("e") is None:
        return None
    psa = norm_sa(plan.get("sa", ""))
    hits = [o for o in opts if o.get("e") == plan.get("e") and norm_sa(o.get("sa", "")) == psa]
    if len(hits) != 1:
        hits = [o for o in opts if o.get("e") == plan.get("e")]
    if len(hits) != 1:
        return None
    o = hits[0]
    return o.get("e"), norm_sa(o.get("sa", "")), o.get("kind")


def build(args) -> None:
    from anvil.bridge.featurize import Featurizer, store_wire_hist
    from anvil.store.trajectories import TrajectoryStore
    from anvil.training.dataset import SCHED_CAP, default_methods, norm_sa

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ck = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    feat = Featurizer(ck["config"]["embed"], default_methods())
    stats = Counter()
    examples: list[dict] = []
    rng = random.Random(20280903)
    t0 = time.monotonic()
    for spath in args.stores:
        st = TrajectoryStore(Path(spath))
        sname = Path(spath).name
        games = st.game_indices()
        if args.max_games:
            games = games[: args.max_games]
        for g in games:
            try:
                traj = st.game(g)
            except Exception:  # noqa: BLE001 — undecodable game
                stats["undecodable"] += 1
                continue
            players = traj.header.get("players") or []
            seats = [i for i, p in enumerate(players) if str(p.get("name", "")).startswith("Anvil")]
            decs = traj.decisions
            prior: list = []
            # own-turn priority windows per (seat, turn), in order
            turns: dict[tuple, list] = {}
            for i, d in enumerate(decs):
                if d.get("m") == "chooseSpellAbilityToPlay" and d.get("p") in seats and d.get("obs"):
                    turns.setdefault((d["p"], d.get("t", 0)), []).append(i)
            for (p, t), idxs in turns.items():
                emis_i = next(
                    (i for i in idxs
                     if decs[i]["obs"].get("glob", {}).get("ph") == "MAIN1"
                     and decs[i]["obs"].get("glob", {}).get("ap") == p),
                    None,
                )
                if emis_i is None:
                    stats["turn_no_main1"] += 1
                    continue
                # the executor's realized (e, sa, kind) at each own window of
                # the turn from the emission window on — the plan's material
                realized = []
                for i in idxs:
                    if i < emis_i:
                        continue
                    ch = _chosen_key(decs[i])
                    if ch is None:
                        continue
                    e, sa, kind = ch
                    if kind == "land" and not args.include_lands:
                        stats["land_skipped"] += 1
                        continue
                    realized.append((i, e, sa))
                # training windows: the emission window (role 'emit') and —
                # the revision decodes' supervision — every later own-turn
                # priority window with obs (role 'later'): target = the
                # executor's REMAINING casts from that window on, in that
                # window's own candidate basis (post-land casts become
                # plannable where they become castable)
                win_idxs = [emis_i] + ([i for i in idxs if i > emis_i] if args.all_windows else [])
                for wi in win_idxs:
                    dec = decs[wi]
                    if wi != emis_i and dec["obs"].get("glob", {}).get("ap") != p:
                        continue
                    wire = dict(dec)
                    if "hist" not in dec:
                        wire["hist"] = store_wire_hist(decs[:wi], dec.get("_pos", wi))
                    try:
                        ex, aux = feat.example(wire, traj.header, "priority")
                    except Exception:  # noqa: BLE001
                        stats["featurize_error"] += 1
                        continue
                    cand_of: dict[tuple, int] = {}
                    opts = dec.get("opts") or []
                    for j, fo in enumerate(aux["cand_first_opt"]):
                        if j == 0 or fo < 0:
                            continue
                        o = opts[fo]
                        cand_of.setdefault((o.get("e"), norm_sa(o.get("sa", ""))), j)
                    slots = []
                    for i, e, sa in realized:
                        if i < wi:
                            continue
                        j = cand_of.get((e, sa))
                        if j is None:
                            stats["unmatched_emit" if wi == emis_i else "unmatched_later"] += 1
                            continue
                        slots.append(j)
                    tgt = torch.full((SCHED_CAP + 1,), -1, dtype=torch.int64)
                    for k, j in enumerate(slots[:SCHED_CAP]):
                        tgt[k] = j
                    if len(slots) < SCHED_CAP:
                        tgt[len(slots)] = 0
                    role = "emit" if wi == emis_i else "later"
                    if role == "later" and not slots and rng.random() > args.later_empty_keep:
                        stats["later_empty_dropped"] += 1
                        continue
                    ex = {k: v for k, v in ex.items() if torch.is_tensor(v)}
                    ex["_sched_tgt"] = tgt
                    ex["_key"] = (sname, g, p, t)
                    ex["_role"] = role
                    examples.append(ex)
                    stats[role] += 1
                    stats["slots_" + role] += len(slots)
                    stats[f"len_{role}_{min(len(slots), 6)}"] += 1
            stats["games"] += 1
            if stats["games"] % 100 == 0:
                print(f"[build] {stats['games']} games, {stats['emit']}+{stats['later']} windows, "
                      f"{time.monotonic() - t0:.0f}s", flush=True)
    for lab in args.certified or []:
        _build_certified(lab, feat, examples, stats, args)
    torch.save({"examples": examples, "stats": dict(stats), "stores": args.stores,
                "certified": args.certified, "include_lands": args.include_lands}, out / "windows.pt")
    for role in ("emit", "later"):
        n = stats[role]
        print(f"[build] {role}: {n} windows; mean len {stats['slots_' + role] / max(n, 1):.2f}; "
              f"lengths {[round(stats[f'len_{role}_{k}'] / max(n, 1), 3) for k in range(7)]}; "
              f"unmatched {stats['unmatched_' + role]}")
    print(f"[build] {stats['games']} games in {time.monotonic() - t0:.0f}s; "
          f"lands_skipped {stats['land_skipped']} -> {out / 'windows.pt'}")


def _build_certified(labels_path: str, feat, examples: list, stats: Counter, args) -> None:
    """The mint's labeled emission windows (ADR-0088/0089 full-support labels:
    per (store, g, t, seat) the search-adjudicated best of {natural line,
    arms}; `arm` 0 = the natural line CONFIRMED, >0 = a CERTIFIED
    improvement). Featurized from the label's own store at the emission
    window (the same first-own-MAIN1 rule); target = the label's (e, sa)
    sequence mapped to that window's candidate basis. Roles: 'cert' /
    'natcf'."""
    from anvil.bridge.featurize import store_wire_hist
    from anvil.store.trajectories import TrajectoryStore
    from anvil.training.dataset import SCHED_CAP, norm_sa

    rows = [json.loads(x) for x in open(labels_path)]
    meta = rows[0] if rows and rows[0].get("k") == "meta" else {}
    rows = [r for r in rows if r.get("k") != "meta"]
    store_path = REPO / meta["store"] if meta.get("store") else None
    if store_path is None or not store_path.exists():
        print(f"[build] certified: store missing for {labels_path}: {meta.get('store')}")
        return
    st = TrajectoryStore(store_path)
    sname = store_path.name
    by_game: dict[int, list] = {}
    for r in rows:
        by_game.setdefault(r["g"], []).append(r)
    for g, labs in by_game.items():
        try:
            traj = st.game(g)
        except Exception:  # noqa: BLE001
            stats["cert_undecodable"] += 1
            continue
        decs = traj.decisions
        for r in labs:
            p, t = r["seat"], r["t"]
            emis_i = next(
                (i for i, d in enumerate(decs)
                 if d.get("m") == "chooseSpellAbilityToPlay" and d.get("p") == p
                 and d.get("t") == t and d.get("obs")
                 and d["obs"].get("glob", {}).get("ph") == "MAIN1"
                 and d["obs"].get("glob", {}).get("ap") == p),
                None,
            )
            if emis_i is None:
                stats["cert_no_window"] += 1
                continue
            dec = decs[emis_i]
            wire = dict(dec)
            if "hist" not in dec:
                wire["hist"] = store_wire_hist(decs[:emis_i], dec.get("_pos", emis_i))
            try:
                ex, aux = feat.example(wire, traj.header, "priority")
            except Exception:  # noqa: BLE001
                stats["cert_featurize_error"] += 1
                continue
            # the mint's label basis is Census.str: (entity, sa[:60]) — the
            # seedlabels loader's key, mirrored exactly
            cand_of: dict[tuple, int] = {}
            opts = dec.get("opts") or []
            for j, fo in enumerate(aux["cand_first_opt"]):
                if j == 0 or fo < 0:
                    continue
                o = opts[fo]
                cand_of.setdefault((o.get("e"), str(o.get("sa") or "")[:60]), j)
            slots = []
            miss = 0
            for e, sa in r.get("seq") or []:
                j = cand_of.get((e, str(sa or "")[:60]))
                if j is None:
                    miss += 1
                    continue
                slots.append(j)
            if miss:
                stats["cert_unmatched_slots"] += miss
            tgt = torch.full((SCHED_CAP + 1,), -1, dtype=torch.int64)
            for k, j in enumerate(slots[:SCHED_CAP]):
                tgt[k] = j
            if len(slots) < SCHED_CAP:
                tgt[len(slots)] = 0
            role = "cert" if r.get("arm", 0) > 0 else "natcf"
            ex = {k: v for k, v in ex.items() if torch.is_tensor(v)}
            ex["_sched_tgt"] = tgt
            ex["_key"] = (sname, g, p, t)
            ex["_role"] = role
            examples.append(ex)
            stats[role] += 1
            stats["slots_" + role] += len(slots)
            stats[f"len_{role}_{min(len(slots), 6)}"] += 1
    for role in ("cert", "natcf"):
        n = stats[role]
        if n:
            print(f"[build] {role} ({sname}): {n} windows; mean len {stats['slots_' + role] / n:.2f}; "
                  f"unmatched slots {stats['cert_unmatched_slots']}")


# ---------------------------------------------------------------------- fit

def _batches(exs: list[dict], bs: int, shuffle: bool, rng: random.Random):
    from anvil.training.dataset import SCHED_CAP, collate

    order = list(range(len(exs)))
    if shuffle:
        rng.shuffle(order)
    for i in range(0, len(order), bs):
        chunk = [exs[j] for j in order[i : i + bs]]
        plain = [{k: v for k, v in e.items() if not k.startswith("_")} for e in chunk]
        b = collate(plain)
        tgt_full = torch.stack([e["_sched_tgt"] for e in chunk])
        b["sched_tgt"] = tgt_full[:, :SCHED_CAP]
        b["sched_tgt_full"] = tgt_full
        yield b


def _eval(net, exs, dev, bs=128) -> dict:
    res = {"all": _eval_role(net, exs, dev, bs)}
    for role in ("emit", "later", "cert", "natcf"):
        sub = [e for e in exs if e.get("_role", "emit") == role]
        if sub:
            res[role] = _eval_role(net, sub, dev, bs)
    return res


def _eval_role(net, exs, dev, bs=128) -> dict:
    import torch.nn.functional as F

    net.eval()
    tot = Counter()
    ce_sum = 0.0
    n_ce = 0
    pred_len = Counter()
    lab_len = Counter()
    with torch.no_grad():
        for b in _batches(exs, bs, False, random.Random(0)):
            b = {k: (v.to(dev) if torch.is_tensor(v) else v) for k, v in b.items()}
            with torch.autocast(dev, dtype=torch.bfloat16):
                fwd = net(b)
                act = net.act(b, sched_decode=True)
            lg = fwd["sched_logits"].float()
            tf = b["sched_tgt_full"]
            ce = F.cross_entropy(lg.flatten(0, 1), tf.flatten(0, 1), ignore_index=-1, reduction="sum")
            ce_sum += float(ce)
            n_ce += int((tf >= 0).sum())
            picks = act["sched_picks"]  # (B, CAP) greedy, 0 = STOP latched
            B = tf.shape[0]
            for i in range(B):
                lab = [int(x) for x in tf[i] if x >= 0]
                lab_seq = [x for x in lab if x > 0]
                pr = [int(x) for x in picks[i]]
                pr_seq = []
                for x in pr:
                    if x == 0:
                        break
                    pr_seq.append(x)
                tot["n"] += 1
                tot["exact"] += pr_seq == lab_seq
                tot["len_match"] += len(pr_seq) == len(lab_seq)
                if lab_seq:
                    tot["n_nonempty"] += 1
                    tot["slot0"] += bool(pr_seq) and pr_seq[0] == lab_seq[0]
                    tot["set_jaccard"] += len(set(pr_seq) & set(lab_seq)) / len(set(pr_seq) | set(lab_seq))
                else:
                    tot["n_empty"] += 1
                    tot["empty_hit"] += not pr_seq
                pred_len[min(len(pr_seq), 6)] += 1
                lab_len[min(len(lab_seq), 6)] += 1
    n = max(tot["n"], 1)
    return {
        "ce": round(ce_sum / max(n_ce, 1), 4),
        "exact": round(tot["exact"] / n, 4),
        "len_match": round(tot["len_match"] / n, 4),
        "slot0_on_nonempty": round(tot["slot0"] / max(tot["n_nonempty"], 1), 4),
        "jaccard_on_nonempty": round(tot["set_jaccard"] / max(tot["n_nonempty"], 1), 4),
        "empty_recall": round(tot["empty_hit"] / max(tot["n_empty"], 1), 4),
        "n": tot["n"],
        "pred_len": [round(pred_len[k] / n, 3) for k in range(7)],
        "label_len": [round(lab_len[k] / n, 3) for k in range(7)],
    }


def fit(args) -> None:
    from anvil.training.dataset import default_methods
    from anvil.training.train import build_net

    out = Path(args.out)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    data = torch.load(out / "windows.pt", weights_only=False)
    exs = data["examples"]
    # degenerate (combo/loop) turns: hundreds of casts in one turn produce
    # hundreds of windows with cap-length targets (12 turns held 5,589 of
    # 151,921 windows and the whole length-6 spike on the first corpus)
    per_turn = Counter(e["_key"] for e in exs)
    big = {k for k, n in per_turn.items() if n > args.max_turn_windows}
    exs = [e for e in exs if e["_key"] not in big]
    print(f"[fit] dropped {len(big)} turns with > {args.max_turn_windows} windows "
          f"({sum(per_turn[k] for k in big)} windows); {len(exs)} remain")
    rng = random.Random(args.seed)
    import hashlib

    def _is_hold(key) -> bool:  # per-game hash: stable across role filters and corpora
        h = int(hashlib.sha1(f"{key[0]}:{key[1]}:{args.seed}".encode()).hexdigest()[:8], 16)
        return (h % 10000) < int(args.holdout * 10000)

    games = sorted({(e["_key"][0], e["_key"][1]) for e in exs})
    hold_games = {g for g in games if _is_hold(g)}
    n_hold = len(hold_games)
    keep = set(args.roles.split(",")) if args.roles else None
    if keep:
        exs = [e for e in exs if e.get("_role", "emit") in keep]
    train = [e for e in exs if (e["_key"][0], e["_key"][1]) not in hold_games]
    hold = [e for e in exs if (e["_key"][0], e["_key"][1]) in hold_games]
    if args.cert_weight > 1:
        extra = [e for e in train if e.get("_role") == "cert"]
        train = train + extra * (args.cert_weight - 1)
    print(f"[fit] {len(train)} train / {len(hold)} holdout windows ({n_hold} holdout games) on {dev}; "
          f"roles {dict(Counter(e.get('_role', 'emit') for e in exs))}")

    ck = torch.load(args.ckpt, map_location=dev, weights_only=False)
    cfg = ck["config"]
    net = build_net(cfg["embed"], cfg["pool_manifest"], len(default_methods()),
                    n_sa=cfg.get("sa_vocab_size", 0)).to(dev)
    net.load_compat(ck["model"])
    net.eval()  # frozen trunk: eval-mode dropout/norm throughout (the executor as served)
    if args.init_from_cast_head:
        # the planner's slot-0 pointer starts as the cast head's own pointer:
        # sched_query's STATE block <- ptr_query (plan/prev blocks zero),
        # sched_key <- ptr_key, sched_sa_proj <- sa_proj. The head's first
        # pick then equals the executor's preference at that window before
        # any fitting; STOP stays a fresh key (pass is the cast head's
        # separate pass_head, not a pointer key).
        with torch.no_grad():
            d = net.ptr_query.weight.shape[1]
            net.sched_query.weight.zero_()
            net.sched_query.weight[:, :d] = net.ptr_query.weight
            net.sched_query.bias.copy_(net.ptr_query.bias)
            net.sched_key.weight.copy_(net.ptr_key.weight)
            net.sched_key.bias.copy_(net.ptr_key.bias)
            if net.sched_sa_proj.weight.shape == net.sa_proj.weight.shape:
                net.sched_sa_proj.weight.copy_(net.sa_proj.weight)
                net.sched_sa_proj.bias.copy_(net.sa_proj.bias)
        print("[fit] planner pointer initialized from the cast head's pointer")
    for name, p in net.named_parameters():
        p.requires_grad_(name.split(".")[0] in HEAD_PARAMS)
    params = [p for p in net.parameters() if p.requires_grad]
    print(f"[fit] trainable params: {sum(p.numel() for p in params)} in {HEAD_PARAMS}")
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.0)
    import torch.nn.functional as F

    day0 = _eval(net, hold, dev)
    print(f"[fit] day-zero holdout: {day0}")
    if args.eval_only:
        return
    hist = [{"epoch": 0, **day0}]
    best = day0["all"]["ce"]
    best_state = {k: v.detach().clone() for k, v in net.state_dict().items()
                  if k.split(".")[0] in HEAD_PARAMS}
    for ep in range(1, args.epochs + 1):
        t0 = time.monotonic()
        run_ce = 0.0
        steps = 0
        for b in _batches(train, args.batch, True, rng):
            b = {k: (v.to(dev) if torch.is_tensor(v) else v) for k, v in b.items()}
            with torch.autocast(dev, dtype=torch.bfloat16):
                fwd = net(b)
            loss = F.cross_entropy(fwd["sched_logits"].float().flatten(0, 1),
                                   b["sched_tgt_full"].flatten(0, 1), ignore_index=-1)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step()
            run_ce += float(loss)
            steps += 1
        ev = _eval(net, hold, dev)
        hist.append({"epoch": ep, "train_ce": round(run_ce / max(steps, 1), 4), **ev})
        print(f"[fit] epoch {ep}: train ce {run_ce / max(steps, 1):.4f} | holdout {ev} "
              f"({time.monotonic() - t0:.0f}s)", flush=True)
        if ev["all"]["ce"] < best:
            best = ev["all"]["ce"]
            best_state = {k: v.detach().clone() for k, v in net.state_dict().items()
                          if k.split(".")[0] in HEAD_PARAMS}
        elif args.patience and ep - max(h["epoch"] for h in hist if h["all"]["ce"] == best) >= args.patience:
            print("[fit] early stop")
            break
    # write the ckpt: the input ckpt with the fitted head params
    model = dict(ck["model"])
    for k, v in best_state.items():
        model[k] = v.cpu()
    ck_out = {**ck, "model": model,
              "distill": {"source_ckpt": args.ckpt, "windows": str(out / "windows.pt"),
                          "stores": data["stores"], "holdout_games": n_hold,
                          "best_holdout_ce": best, "history": hist,
                          "head_params": HEAD_PARAMS, "include_lands": data.get("include_lands")}}
    torch.save(ck_out, out / "last.pt")
    json.dump({"history": hist, "best_holdout_ce": best, "train": len(train), "holdout": len(hold)},
              open(out / "metrics.json", "w"), indent=2)
    print(f"[fit] best holdout ce {best:.4f} -> {out / 'last.pt'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", required=True)
    b.add_argument("--stores", nargs="+", required=True)
    b.add_argument("--ckpt", default=str(REPO / "data/training/m10-sched-init/last.pt"),
                   help="featurizer config source (embed manifest)")
    b.add_argument("--max-games", type=int, default=0, help="per store")
    b.add_argument("--include-lands", action="store_true")
    b.add_argument("--certified", nargs="*", default=None,
                   help="mint labels-full.jsonl files (their emission windows join as roles cert/natcf)")
    b.add_argument("--later-empty-keep", type=float, default=0.3,
                   help="keep fraction of LATER windows whose target is empty (class balance + memory)")
    b.add_argument("--no-all-windows", dest="all_windows", action="store_false",
                   help="emission windows only (default: every own-turn priority window)")
    b.set_defaults(fn=build)
    f = sub.add_parser("fit")
    f.add_argument("--out", required=True)
    f.add_argument("--ckpt", default=str(REPO / "data/training/m10-sched-init/last.pt"))
    f.add_argument("--epochs", type=int, default=8)
    f.add_argument("--lr", type=float, default=1e-3)
    f.add_argument("--batch", type=int, default=64)
    f.add_argument("--holdout", type=float, default=0.1)
    f.add_argument("--patience", type=int, default=2)
    f.add_argument("--seed", type=int, default=20280903)
    f.add_argument("--max-turn-windows", type=int, default=40)
    f.add_argument("--init-from-cast-head", action="store_true")
    f.add_argument("--roles", default=None, help="csv of roles to train/eval on (default all)")
    f.add_argument("--cert-weight", type=int, default=1, help="oversample 'cert' windows k-fold")
    f.add_argument("--eval-only", action="store_true", help="report the ckpt's holdout numbers, no fit")
    f.set_defaults(fn=fit)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
