"""M6 D2-B lever B-2 — the partial-unfreeze ranking probe (ADR-0042).

Question: can gradient pressure on the trunk's own weights learn the
live-vs-dead ranking the frozen `[STATE]` provably cannot linearly express
(plateau 0.43-0.46, ADR-0041) and derived-feature enrichment cannot add
(B-1, ADR-0043 — `[STATE]` already encodes the arithmetic)?

Recipe (pre-registered in ADR-0042 decision 1): unfreeze the top-N trunk
layers + the value head (sweep N; N=0 = trained-head-on-frozen-trunk
control), ranking-first loss (RankNet pairwise logistic, |Δwr|-weighted,
pairs gated at >= 2/8 — one K=8 rollout step apart is noise) on the
benchmark's train split, early-stopped on a game-grouped inner validation
split, final read on the SAME frozen holdout as every other candidate.

Gate (standing, ADR-0041): beat the 0.455 ridge / ~0.46 plateau on
`frozen-probe-ext2-c2` c2. Era-scoped by construction: rollout labels are
policy-conditional, so the fine-tune consumes c2 (iter-019-era) labels on
the iter-019 ckpt; any ckpt this probe graduates is a NEW ERA for
era-scoped assets per standing rules.

The examples are the exact frozen-probe positions (same turn-join
convention, ValueEvaluator masked-path windows — what the policy-side value
head actually consumes); `prep` banks them once, `sweep` reuses.

Usage:
  uv run python scripts/unfreeze_probe.py prep \
      --out data/runs/unfreeze-probe-v1
  uv run python scripts/unfreeze_probe.py sweep \
      --out data/runs/unfreeze-probe-v1        # N x lr grid, report per cell
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frozen_probe as fp  # noqa: E402  (split/spearman of record)

DATASET = "data/runs/frozen-probe-ext2-c2/dataset.jsonl"
CKPT = "data/training/d6-run11/iter-019/train/last.pt"
ERA = "c2"  # the gate era; c1 labels are run9-era policy
PAIR_GATE = 0.2  # min |Δwr| for a ranking pair (2/8 = 0.25 > it)
RIDGE_PLATEAU = 0.4552  # the number to beat (ADR-0041/0043)


def _inner_val(game: str) -> bool:
    # game-grouped inner split for early stopping (train games only);
    # same idiom as frozen_probe._mlp_fit_pred
    return hashlib.sha256(f"uvval:{game}".encode()).digest()[0] % 7 == 0


# ---------------------------------------------------------------- prep


def collect_examples(positions: list[tuple[str, int, int]], ev) -> tuple[list[str], list[dict]]:
    """(store, g, t) positions -> aligned (keys, masked-path value windows),
    via the exact frozen-probe turn-join convention. Loud on any miss."""
    from anvil.store.trajectories import TrajectoryStore

    by_store: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for store, g, t in positions:
        by_store[store].append((g, t))
    keys, exs, missed = [], [], []
    for store, wants in sorted(by_store.items()):
        ts = TrajectoryStore(Path("data/trajectories") / store)
        seat = fp._seat_of(store)
        for g in sorted({g for g, _ in wants}):
            traj = ts.game(g)
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
                keys.append(f"{store}:{g}:{t}")
                exs.append(ev.example(traj.decisions[i], traj.header, seat, traj.decisions[:i]))
    if missed:
        raise SystemExit(
            f"[collect] {len(missed)} positions missed the "
            f"turn join, e.g. {missed[:3]} — convention drift, "
            "refusing a partial bank"
        )
    return keys, exs


def prep(args: argparse.Namespace) -> None:
    import torch

    from anvil.ante.ledger import ValueEvaluator

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = fp.load_rows(args.dataset)
    positions = sorted({(r["store"], r["g"], r["t"]) for r in rows})
    print(f"[prep] {len(rows)} labels -> {len(positions)} positions")

    # --full-vis (hidden-info probe): omniscient windows over the policy
    # ckpt — the masked-vs-full-vis delta under identical training prices
    # the belief head / omniscient-critic headroom. Value instrument only.
    ev = ValueEvaluator(CKPT, full_vis=True if args.full_vis else None)
    assert ev.full_vis == bool(args.full_vis), "B-2's default is the masked policy-side path"
    t0 = time.time()
    keys, exs = collect_examples(positions, ev)
    torch.save(
        {
            "keys": keys,
            "examples": exs,
            "ckpt": CKPT,
            "dataset": args.dataset,
            "full_vis": bool(args.full_vis),
        },
        out_dir / "examples.pt",
    )
    print(f"[prep] {len(keys)} examples banked in {time.time() - t0:.0f}s -> {out_dir}/examples.pt")


# ---------------------------------------------------------------- sweep


def _scores(net, examples: list, idxs: np.ndarray, device: str, batch: int) -> np.ndarray:
    import torch

    from anvil.training.dataset import collate

    net.eval()
    out = np.empty(len(idxs), dtype=np.float64)
    with torch.no_grad():
        for i in range(0, len(idxs), batch):
            chunk = collate([examples[j] for j in idxs[i : i + batch]])
            chunk = {k: v.to(device) for k, v in chunk.items()}
            with torch.autocast(device, dtype=torch.bfloat16):
                card_vecs = net.cards(chunk["ent_emb"])
                tokens, pad = net.assemble(card_vecs, chunk)
                h = net.trunk(tokens, src_key_padding_mask=pad)
                v = net.value_head(h[:, 0]).squeeze(-1)
            out[i : i + len(v)] = v.float().cpu().numpy()
    return out


def _rank_loss(scores, y, device):
    """RankNet pairwise logistic over within-batch pairs, |Δwr|-weighted,
    gated at PAIR_GATE (K=8 labels quantize at 1/8 — one-step pairs are
    noise). Returns None when the batch has no usable pair."""
    import torch

    dy = y.unsqueeze(0) - y.unsqueeze(1)  # y_i - y_j
    mask = dy > PAIR_GATE  # i outranks j
    if not mask.any():
        return None
    ds = scores.unsqueeze(0) - scores.unsqueeze(1)
    w = dy[mask]
    return (torch.nn.functional.softplus(-ds[mask]) * w).sum() / w.sum()


def _cell(
    n_unfreeze: int,
    lr: float,
    examples: list,
    row_idx: np.ndarray,
    y: np.ndarray,
    games: np.ndarray,
    ho: np.ndarray,
    args,
) -> dict:
    import torch

    from anvil.ante.ledger import ValueEvaluator
    from anvil.training.dataset import collate

    torch.manual_seed(args.seed)
    device = "cuda"
    ev = ValueEvaluator(CKPT)
    net = ev.net
    n_layers = len(net.trunk.layers)
    for name, p in net.named_parameters():
        p.requires_grad = name.startswith("value_head") or any(
            name.startswith(f"trunk.layers.{i}.") for i in range(n_layers - n_unfreeze, n_layers)
        )
    n_train_p = sum(p.numel() for p in net.parameters() if p.requires_grad)
    opt = torch.optim.AdamW(
        [p for p in net.parameters() if p.requires_grad], lr=lr, weight_decay=0.01
    )

    # inner_pool (ck1 lesson, 2026-08-08): early stopping must target the
    # FROZEN holdout's distribution. When train labels grow beyond the
    # base population (offset-heavy tranche labels), an all-games inner
    # split drifts and stops training tuned for the wrong mix — measured
    # as a phantom -0.023 holdout regression. Restrict inner-val
    # eligibility to the base population; extension labels are train-only.
    pool = getattr(args, "inner_pool", None)
    inner = np.array([_inner_val(g) and (pool is None or g in pool) for g in games])
    tr = np.where(~ho & ~inner)[0]
    if args.train_size:  # label-scaling curve: game-grouped subsample
        tr = tr[fp._curve_subset(games[tr], args.train_size)]
    iv = np.where(~ho & inner)[0]
    te = np.where(ho)[0]
    print(
        f"[cell N={n_unfreeze} lr={lr:g}] params {n_train_p:,} | rows "
        f"train {len(tr)} inner-val {len(iv)} holdout {len(te)}",
        flush=True,
    )

    base = fp.spearman(_scores(net, examples, row_idx[te], device, args.batch), y[te])
    best_s, best_state, patience, epoch = -2.0, None, 0, 0
    rng = np.random.default_rng(args.seed)
    t0 = time.time()
    while epoch < args.max_epochs:
        epoch += 1
        net.train()
        perm = rng.permutation(tr)
        for i in range(0, len(perm), args.batch):
            sel = perm[i : i + args.batch]
            if len(sel) < 8:
                continue
            chunk = collate([examples[j] for j in row_idx[sel]])
            chunk = {k: v.to(device) for k, v in chunk.items()}
            yb = torch.tensor(y[sel], dtype=torch.float32, device=device)
            with torch.autocast(device, dtype=torch.bfloat16):
                card_vecs = net.cards(chunk["ent_emb"])
                tokens, pad = net.assemble(card_vecs, chunk)
                h = net.trunk(tokens, src_key_padding_mask=pad)
                v = net.value_head(h[:, 0]).squeeze(-1)
                loss = _rank_loss(v.float(), yb, device)
            if loss is None:
                continue
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
        s = fp.spearman(_scores(net, examples, row_idx[iv], device, args.batch), y[iv])
        if s > best_s:
            best_s, patience = s, 0
            best_state = {
                k: v.detach().clone().cpu()
                for k, v in net.state_dict().items()
                if k.startswith("value_head") or k.startswith("trunk.")
            }
        else:
            patience += 1
            if patience >= args.patience:
                break
        if epoch % 10 == 0:
            print(
                f"[cell N={n_unfreeze} lr={lr:g}] epoch {epoch}: "
                f"inner-val {s:.4f} (best {best_s:.4f})",
                flush=True,
            )
    if best_state is not None:
        net.load_state_dict(best_state, strict=False)
    ho_s = fp.spearman(_scores(net, examples, row_idx[te], device, args.batch), y[te])
    captured = None
    if getattr(args, "capture_state", False):
        captured = {k: v.detach().cpu() for k, v in net.state_dict().items()}
    res = {
        "n_unfreeze": n_unfreeze,
        "lr": lr,
        "trainable_params": n_train_p,
        "epochs": epoch,
        "baseline_holdout": round(base, 4),
        "best_inner_val": round(best_s, 4),
        "holdout_spearman": round(ho_s, 4),
        "beats_plateau": bool(ho_s > RIDGE_PLATEAU),
        "wall_min": round((time.time() - t0) / 60, 1),
    }
    print(
        f"[cell N={n_unfreeze} lr={lr:g}] DONE holdout {ho_s:.4f} "
        f"(trained-head baseline {base:.4f}, plateau {RIDGE_PLATEAU}) "
        f"in {res['wall_min']}min",
        flush=True,
    )
    if captured is not None:
        res["_state"] = captured
    del net, ev, opt
    import torch as _t

    _t.cuda.empty_cache()
    return res


def sweep(args: argparse.Namespace) -> None:
    import torch

    out_dir = Path(args.out)
    bank = torch.load(out_dir / "examples.pt", weights_only=False)
    keys, examples = bank["keys"], bank["examples"]
    key_idx = {k: i for i, k in enumerate(keys)}

    rows = [r for r in fp.load_rows(args.dataset) if r["era"] == args.era]
    args.inner_pool = None
    if args.inner_pool_dataset:
        pool_rows = [r for r in fp.load_rows(args.inner_pool_dataset) if r["era"] == args.era]
        pool_keys = {(r["store"], r["g"], r["t"], r["src"]) for r in pool_rows}
        # a game that gained extension labels moves wholly to train —
        # else it spans train and inner-val (game-grouping violation)
        ext_games = {
            f"{r['store']}:{r['g']}"
            for r in rows
            if (r["store"], r["g"], r["t"], r["src"]) not in pool_keys
        }
        args.inner_pool = {f"{r['store']}:{r['g']}" for r in pool_rows} - ext_games
        print(
            f"[sweep] inner-val pool: {len(args.inner_pool)} "
            f"extension-free base games (from {args.inner_pool_dataset})"
        )
    row_idx = np.array([key_idx[f"{r['store']}:{r['g']}:{r['t']}"] for r in rows])
    y = np.array([r["wr"] for r in rows])
    games = np.array([f"{r['store']}:{r['g']}" for r in rows])
    ho = np.array([fp._held_out(r["store"], r["g"]) for r in rows])
    print(
        f"[sweep] era {args.era}: {len(rows)} label rows, "
        f"{ho.sum()} holdout; grid N={args.ns} lr={args.lrs}"
    )

    report = {
        "constants": {
            "gate": f"beat {RIDGE_PLATEAU} ridge / ~0.46 plateau on the frozen "
            "benchmark holdout (ADR-0041/0043)",
            "ckpt": CKPT,
            "era": args.era,
            "pair_gate": PAIR_GATE,
            "loss": "RankNet pairwise logistic, |dwr|-weighted",
            "note": "any graduating ckpt is a NEW ERA for era-scoped assets",
        },
        "cells": [],
    }
    report_name = args.report or "unfreeze-probe-report.json"
    for n in [int(x) for x in args.ns.split(",")]:
        for lr in [float(x) for x in args.lrs.split(",")]:
            for seed in [int(x) for x in args.seeds.split(",")]:
                args.seed = seed
                res = {
                    **_cell(n, lr, examples, row_idx, y, games, ho, args),
                    "seed": seed,
                    "train_size": args.train_size,
                }
                report["cells"].append(res)
                (out_dir / report_name).write_text(json.dumps(report, indent=2) + "\n")
    best = max(report["cells"], key=lambda c: c["holdout_spearman"])
    print(
        f"[sweep] BEST N={best['n_unfreeze']} lr={best['lr']:g} "
        f"seed={best.get('seed', 0)}: "
        f"holdout {best['holdout_spearman']} "
        f"({'CLEARS' if best['beats_plateau'] else 'does NOT clear'} "
        f"the {RIDGE_PLATEAU} gate)"
    )
    try:
        from anvil.training.notify import notify

        notify(
            "unfreeze probe sweep done",
            f"best N={best['n_unfreeze']} lr={best['lr']:g} "
            f"holdout {best['holdout_spearman']} vs gate {RIDGE_PLATEAU}",
        )
    except Exception:
        pass


def build(args: argparse.Namespace) -> None:
    """The graduated critic asset (ADR-0046 decision 1 / user-approved
    value-tower path): train N=4 ranking fine-tunes across seeds on the
    full train split, select by INNER-VAL (never by holdout — the frozen
    benchmark stays a pure reporting read), save a loadable checkpoint in
    the finetune_value.py format. The saved net is a CRITIC: its policy
    heads sit on a ranking-fine-tuned trunk — never serve policy from it
    (d4-critic-fullvis precedent). Era-scoped by construction; consumers
    are curation/doom/eval instruments."""
    import datetime as _dt

    import torch

    out_dir = Path(args.out)
    bank = torch.load(Path(args.bank) / "examples.pt", weights_only=False)
    keys, examples = list(bank["keys"]), list(bank["examples"])
    assert not bank.get("full_vis"), "the critic asset is the MASKED path"
    key_idx = {k: i for i, k in enumerate(keys)}
    rows = [r for r in fp.load_rows(args.dataset) if r["era"] == args.era]
    args.inner_pool = None
    if args.inner_pool_dataset:
        pool_rows = [r for r in fp.load_rows(args.inner_pool_dataset) if r["era"] == args.era]
        pool_keys = {(r["store"], r["g"], r["t"], r["src"]) for r in pool_rows}
        ext_games = {
            f"{r['store']}:{r['g']}"
            for r in rows
            if (r["store"], r["g"], r["t"], r["src"]) not in pool_keys
        }
        args.inner_pool = {f"{r['store']}:{r['g']}" for r in pool_rows} - ext_games
    row_idx = np.array([key_idx[f"{r['store']}:{r['g']}:{r['t']}"] for r in rows])
    y = np.array([r["wr"] for r in rows])
    games = np.array([f"{r['store']}:{r['g']}" for r in rows])
    ho = np.array([fp._held_out(r["store"], r["g"]) for r in rows])

    args.capture_state = True
    best, cells = None, []
    for seed in [int(s) for s in args.seeds.split(",")]:
        args.seed = seed
        res = _cell(args.n, args.lr, examples, row_idx, y, games, ho, args)
        state = res.pop("_state")
        cells.append({**res, "seed": seed})
        if best is None or res["best_inner_val"] > best[1]["best_inner_val"]:
            best = (state, {**res, "seed": seed})
    state, chosen = best

    base = torch.load(CKPT, map_location="cpu", weights_only=False)
    config = {
        **base["config"],
        "value_finetune": {
            "mode": "ranking-unfreeze",
            "base_ckpt": CKPT,
            "base_step": base.get("step"),
            "n_unfreeze": args.n,
            "lr": args.lr,
            "labelset": args.dataset,
            "era": args.era,
            "loss": f"RankNet pairwise, |dwr|-weighted, gate {PAIR_GATE}",
            "selection": "best inner-val across seeds (holdout untouched)",
            "chosen_seed": chosen["seed"],
            "inner_val": chosen["best_inner_val"],
            "holdout_spearman_report": chosen["holdout_spearman"],
            "created": _dt.date.today().isoformat(),
            "note": "CRITIC ckpt — ranking-fine-tuned trunk top-N; never "
            "serve policy from it (value-tower discipline, "
            "ADR-0046/user 2026-08-08)",
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save({"step": base.get("step"), "model": state, "config": config}, out_dir / "last.pt")
    (out_dir / "build-report.json").write_text(
        json.dumps(
            {
                "cells": cells,
                "chosen_seed": chosen["seed"],
                "config_stamp": config["value_finetune"],
            },
            indent=2,
        )
        + "\n"
    )
    print(
        f"[build] chosen seed {chosen['seed']} (inner-val "
        f"{chosen['best_inner_val']}, holdout report "
        f"{chosen['holdout_spearman']}) -> {out_dir}/last.pt"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prep")
    p.add_argument("--out", required=True)
    p.add_argument("--dataset", default=DATASET)
    p.add_argument(
        "--full-vis",
        action="store_true",
        help="omniscient windows (hidden-info probe; value instrument only)",
    )
    p.set_defaults(fn=prep)
    p = sub.add_parser("sweep")
    p.add_argument("--out", required=True)
    p.add_argument("--dataset", default=DATASET)
    p.add_argument("--era", default=ERA)
    p.add_argument(
        "--ns",
        default="0,1,2,4",
        help="comma list of top-N trunk layers to unfreeze (0 = value-head-only control)",
    )
    p.add_argument("--lrs", default="1e-4,3e-5")
    p.add_argument("--batch", type=int, default=192)
    p.add_argument("--max-epochs", type=int, default=200)
    p.add_argument("--patience", type=int, default=15)
    p.add_argument(
        "--inner-pool-dataset",
        default=None,
        help="restrict inner-val (early-stop) games to this "
        "dataset's population — REQUIRED for comparable "
        "reads when --dataset extends the base labels "
        "(the ck1 early-stop-drift lesson)",
    )
    p.add_argument(
        "--train-size",
        type=int,
        default=None,
        help="cap train rows (game-grouped subsample) for the label-scaling curve",
    )
    p.add_argument("--seeds", default="0", help="comma list; each (N, lr) cell runs once per seed")
    p.add_argument(
        "--report", default=None, help="report filename (default unfreeze-probe-report.json)"
    )
    p.set_defaults(fn=sweep)
    p = sub.add_parser("build")
    p.add_argument("--out", required=True, help="critic ckpt output dir")
    p.add_argument("--bank", required=True, help="dir holding the masked examples.pt for --dataset")
    p.add_argument("--dataset", default=DATASET)
    p.add_argument("--era", default=ERA)
    p.add_argument("--n", type=int, default=4)
    p.add_argument("--lr", type=float, default=3e-5)
    p.add_argument("--seeds", default="0,1,2")
    p.add_argument("--batch", type=int, default=192)
    p.add_argument("--max-epochs", type=int, default=200)
    p.add_argument("--patience", type=int, default=15)
    p.add_argument("--train-size", type=int, default=None)
    p.add_argument("--inner-pool-dataset", default="data/runs/frozen-probe-ext2-c2/dataset.jsonl")
    p.set_defaults(fn=build)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
