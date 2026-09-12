"""M12 Build 3 evening 4 (ADR-0105): the pay head's fit on the payment
sub-row pool — distillation only (anvil.training.pay_distill: the
asymmetric target over the search's end-of-turn leaf values; the M9 pin
bars imitation and imitation would be empty anyway, auto is the head's
init). Cross-fit by GAME SEED (standing rule): the pool's games hash into
--folds folds, each fold's read comes from the model that never saw it;
--build fits on every row and writes the checkpoint the server serves.

What is trainable (--unfreeze):
  pay     the payment parameters only (pay_bias, pay_kind_emb, pay_mark_emb
          — the M9 Option-A head: no new pointer, the goal-kind embedding
          joins the shared pointer key; every other window is byte-identical
          to the input checkpoint)
  N       + the top-N trunk layers (the priority drift read is the Build 1
          cells', not here — use with a drift read)

The read keeps ties and positives apart (ADR-0069): per fold, before and
after the fit — the cross-entropy to the target, the positive rows' top-1
agreement with the search's best answer and deviation rate, the tie rows'
deviation rate (the false-positive channel). The learnability question of
the evening: does the fitted head deviate where a goal clears the bar and
stay auto where none does?

Usage:
  uv run python -m anvil.training.pay_fit --run data/runs/b3-surflab3-<ts> --out data/runs/build3-e4 --fold 0
  uv run python -m anvil.training.pay_fit ... --read
  uv run python -m anvil.training.pay_fit ... --build --ckpt-out data/training/m12-build3-e4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CKPT = "data/training/m12-build3-e3/last.pt"
ABIL = "data/embeddings/abil-cf2ca6ba-qwen3"
EMBED = "data/embeddings/cf2ca6ba-qwen3"


def fold_of_seed(seed: int, folds: int) -> int:
    h = hashlib.sha1(f"pay:{seed}".encode()).digest()
    return int.from_bytes(h[:4], "little") % folds


class SeedFold:
    """Picklable per-game-seed fold predicate."""

    def __init__(self, folds: int, fold: int | None, split: str):
        self.folds, self.fold, self.split = folds, fold, split

    def __call__(self, seed: int) -> bool:
        if self.fold is None:
            return True
        f = fold_of_seed(seed, self.folds)
        return (f == self.fold) if self.split == "test" else (f != self.fold)


def set_trainable(net, unfreeze: str) -> int:
    n_layers = len(net.trunk.layers)
    top: set[int] = set()
    if unfreeze != "pay":
        top = set(range(n_layers - int(unfreeze), n_layers))
    for name, p in net.named_parameters():
        p.requires_grad = name.startswith("pay_") or any(name.startswith(f"trunk.layers.{i}.") for i in top)
    return sum(p.numel() for p in net.parameters() if p.requires_grad)


def _to(chunk: dict, device: str) -> dict:
    return {k: v.to(device, non_blocking=True) for k, v in chunk.items()}


def evaluate(net, loader, device: str) -> dict:
    import torch

    from anvil.training.pay_distill import pay_distill_loss

    acc: Counter = Counter()
    with torch.no_grad():
        for batch in loader:
            b = _to(batch, device)
            _loss, st = pay_distill_loss(net(b), b)
            n, npos = st["n"], st["n_pos"]
            acc["n"] += n
            acc["n_pos"] += npos
            acc["ce"] += st["pay_ce"] * n
            if npos:
                acc["pos_ce"] += st["pos_ce"] * npos
                acc["pos_top1"] += st["pos_top1"] * npos
                acc["pos_dev"] += st["pos_dev"] * npos
            nt = n - npos
            if nt:
                acc["tie_ce"] += st["tie_ce"] * nt
                acc["tie_dev"] += st["tie_dev"] * nt
            for k in ("dev_n_pos", "dev_gain_pos", "dev_n_tie", "dev_gain_tie", "best_n_pos", "best_gain_pos"):
                acc[k] += st.get(k, 0)
    n = max(1, acc["n"])
    npos = max(1, acc["n_pos"])
    nt = max(1, acc["n"] - acc["n_pos"])
    out = {
        "n": acc["n"],
        "n_pos": acc["n_pos"],
        "ce": round(acc["ce"] / n, 4),
        "pos_ce": round(acc["pos_ce"] / npos, 4),
        "pos_top1": round(acc["pos_top1"] / npos, 4),
        "pos_dev": round(acc["pos_dev"] / npos, 4),
        "tie_ce": round(acc["tie_ce"] / nt, 4),
        "tie_dev": round(acc["tie_dev"] / nt, 4),
    }
    # the pick-vs-leaf read: mean leaf gain (pick − auto) over the head's
    # deviations, positives / ties, and the oracle gain on positives
    for name in ("pos", "tie"):
        k = acc[f"dev_n_{name}"]
        out[f"dev_n_{name}"] = int(k)
        out[f"dev_gain_{name}"] = round(acc[f"dev_gain_{name}"] / k, 4) if k else None
    out["best_gain_pos"] = round(acc["best_gain_pos"] / acc["best_n_pos"], 4) if acc["best_n_pos"] else None
    return out


def make_dataset(a, split: str, folds: int, fold: int | None, shuffle: bool):
    from anvil.training.pay_distill import PaySubRows

    return PaySubRows(
        REPO / a.run, REPO / a.embed, REPO / a.abilities, bar=a.bar, temp=a.temp, min_rolls=a.min_rolls,
        seed=a.seed, shuffle=shuffle, max_rows=a.max_rows, seed_filter=SeedFold(folds, fold, split),
    )


def fit(a) -> None:
    import torch
    from torch.utils.data import DataLoader

    from anvil.training.pay_distill import collate_pay, pay_distill_loss
    from anvil.training.surface_fit import load_net

    device = "cuda"
    torch.manual_seed(a.seed)
    out_dir = REPO / a.out
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = "build" if a.build else f"fold{a.fold}"
    log = (out_dir / f"payfit-{tag}.jsonl").open("w")
    net, ck = load_net(a.ckpt, device)
    n_tr = set_trainable(net, a.unfreeze)
    print(f"[pay_fit {tag}] trainable {n_tr:,} (unfreeze={a.unfreeze}) bar {a.bar} T {a.temp} rolls>={a.min_rolls}", flush=True)
    opt = torch.optim.AdamW([p for p in net.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.0)
    ds_tr = make_dataset(a, "train", a.folds, None if a.build else a.fold, shuffle=True)
    loader = DataLoader(ds_tr, batch_size=a.batch, collate_fn=collate_pay, num_workers=a.workers,
                        persistent_workers=a.workers > 0)
    res: dict = {"tag": tag, "unfreeze": a.unfreeze, "lr": a.lr, "bar": a.bar, "temp": a.temp,
                 "min_rolls": a.min_rolls, "pos_weight": a.pos_weight, "run": a.run, "ckpt": a.ckpt}
    te_loader = None
    if not a.build:
        ds_te = make_dataset(a, "test", a.folds, a.fold, shuffle=False)
        te_loader = DataLoader(ds_te, batch_size=a.batch, collate_fn=collate_pay, num_workers=min(a.workers, 2))
        net.eval()
        res["before"] = evaluate(net, te_loader, device)
        print(f"[pay_fit {tag}] before: {res['before']}", flush=True)
    step = 0
    t0 = time.time()
    epoch = 0
    done = False
    while not done:
        net.train()
        n_in_epoch = 0
        for batch in loader:
            b = _to(batch, device)
            loss, st = pay_distill_loss(net(b), b, pos_weight=a.pos_weight)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for p in net.parameters() if p.requires_grad], 1.0)
            opt.step()
            step += 1
            n_in_epoch += 1
            if step % 20 == 0:
                rec = {"step": step, "epoch": epoch, "t": round(time.time() - t0),
                       **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in st.items()}}
                log.write(json.dumps(rec) + "\n")
                log.flush()
                if step % 200 == 0:
                    print(f"[pay_fit {tag}] {rec}", flush=True)
            if step >= a.steps:
                done = True
                break
        if n_in_epoch == 0:
            raise SystemExit(f"[pay_fit] no payment sub rows under {a.run} (counts {dict(ds_tr.counts)})")
        epoch += 1
        if epoch >= a.epochs:
            done = True
    res.update({"steps": step, "epochs": epoch, "wall_s": round(time.time() - t0),
                "train_counts": dict(ds_tr.counts)})
    if te_loader is not None:
        net.eval()
        res["after"] = evaluate(net, te_loader, device)
        print(f"[pay_fit {tag}] after: {res['after']}", flush=True)
    m = net.state_dict()
    from anvil.training.dataset import TASKS

    res["pay_params"] = {
        "bias": round(float(m["pay_bias"][TASKS["pay_class"]]), 4),
        "kind_emb_norm": round(float(m["pay_kind_emb.weight"].norm()), 4),
        "mark_norm": round(float(m["pay_mark_emb"].norm()), 4),
    }
    if a.build:
        cfg = dict(ck["config"])
        cfg["pay_fit"] = {"steps": step, "unfreeze": a.unfreeze, "lr": a.lr, "bar": a.bar, "temp": a.temp,
                          "min_rolls": a.min_rolls, "pos_weight": a.pos_weight, "run": a.run, "parent": a.ckpt}
        ck_out = REPO / a.ckpt_out
        ck_out.mkdir(parents=True, exist_ok=True)
        torch.save({"step": ck.get("step", 0), "model": net.state_dict(), "config": cfg}, ck_out / "last.pt")
        res["ckpt_out"] = str(ck_out / "last.pt")
        print(f"[pay_fit build] -> {ck_out / 'last.pt'}", flush=True)
    (out_dir / f"payfit-result-{tag}.json").write_text(json.dumps(res, indent=1) + "\n")


def eval_only(a) -> None:
    """The pick-vs-leaf read on a checkpoint: no training, the pool (or one
    fold's held-out slice with --fold) valued by the leaf where the head
    deviates. Writes payfit-eval-<tag>.json under --out."""
    from torch.utils.data import DataLoader

    from anvil.training.pay_distill import collate_pay
    from anvil.training.surface_fit import load_net

    device = "cuda"
    out_dir = REPO / a.out
    out_dir.mkdir(parents=True, exist_ok=True)
    net, _ck = load_net(a.ckpt, device)
    net.eval()
    ds = make_dataset(a, "test", a.folds, a.fold, shuffle=False) if a.fold is not None and a.fold >= 0 \
        else make_dataset(a, "all", a.folds, None, shuffle=False)
    loader = DataLoader(ds, batch_size=a.batch, collate_fn=collate_pay, num_workers=min(a.workers, 2))
    res = evaluate(net, loader, device)
    tag = a.eval_tag or Path(a.ckpt).parent.name
    res.update({"ckpt": a.ckpt, "run": a.run, "bar": a.bar, "temp": a.temp, "min_rolls": a.min_rolls,
                "fold": a.fold, "counts": dict(ds.counts)})
    (out_dir / f"payfit-eval-{tag}.json").write_text(json.dumps(res, indent=1) + "\n")
    print(f"[pay_fit eval {tag}] {res}", flush=True)


def read(a) -> None:
    out_dir = REPO / a.out
    folds = sorted(out_dir.glob("payfit-result-fold*.json"))
    pooled: dict[str, Counter] = {"before": Counter(), "after": Counter()}
    per_fold = []
    for f in folds:
        r = json.loads(f.read_text())
        per_fold.append({"tag": r["tag"], "before": r.get("before"), "after": r.get("after"), "pay": r.get("pay_params")})
        for stage in ("before", "after"):
            v = r.get(stage)
            if not v:
                continue
            c = pooled[stage]
            n, npos = v["n"], v["n_pos"]
            nt = n - npos
            c["n"] += n
            c["n_pos"] += npos
            c["ce"] += v["ce"] * n
            c["pos_ce"] += v["pos_ce"] * npos
            c["pos_top1"] += v["pos_top1"] * npos
            c["pos_dev"] += v["pos_dev"] * npos
            c["tie_ce"] += v["tie_ce"] * nt
            c["tie_dev"] += v["tie_dev"] * nt
    out: dict = {"folds": len(folds), "per_fold": per_fold}
    for stage, c in pooled.items():
        n, npos, nt = max(1, c["n"]), max(1, c["n_pos"]), max(1, c["n"] - c["n_pos"])
        out[stage] = {"n": c["n"], "n_pos": c["n_pos"], "ce": round(c["ce"] / n, 4),
                      "pos_ce": round(c["pos_ce"] / npos, 4), "pos_top1": round(c["pos_top1"] / npos, 4),
                      "pos_dev": round(c["pos_dev"] / npos, 4), "tie_ce": round(c["tie_ce"] / nt, 4),
                      "tie_dev": round(c["tie_dev"] / nt, 4)}
    (out_dir / "payfit-read.json").write_text(json.dumps(out, indent=1) + "\n")
    lines = [f"# pay_fit cross-fit read ({len(folds)} folds)", "",
             "| stage | n | positives | CE | pos CE | pos top-1 | pos dev | tie CE | tie dev |",
             "|---|---|---|---|---|---|---|---|---|"]
    for stage in ("before", "after"):
        v = out[stage]
        lines.append(f"| {stage} | {v['n']} | {v['n_pos']} | {v['ce']} | {v['pos_ce']} | {v['pos_top1']} | {v['pos_dev']} | {v['tie_ce']} | {v['tie_dev']} |")
    (out_dir / "payfit-read.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True, help="the label run dir (workers/inv-*/labels.jsonl) or a flat smoke dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--ckpt", default=CKPT)
    ap.add_argument("--ckpt-out", default="data/training/m12-build3-e4")
    ap.add_argument("--embed", default=EMBED)
    ap.add_argument("--abilities", default=ABIL)
    ap.add_argument("--bar", type=float, default=0.03, help="margin bar (win-prob units) above which a window is a positive")
    ap.add_argument("--temp", type=float, default=0.025, help="leaf-value softmax temperature on positives")
    ap.add_argument("--min-rolls", type=int, default=2, help="valued rolls an answer needs to count")
    ap.add_argument("--pos-weight", type=float, default=1.0, help="loss weight on positive rows (the pool is mostly ties)")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--fold", type=int, default=0)
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--read", action="store_true")
    ap.add_argument("--eval", action="store_true", help="the pick-vs-leaf read on --ckpt (no training); --fold -1 = the whole pool")
    ap.add_argument("--eval-tag", default=None)
    ap.add_argument("--unfreeze", default="pay", help="pay | <N top trunk layers>")
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--max-rows", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    if a.read:
        read(a)
    elif a.eval:
        eval_only(a)
    else:
        fit(a)


if __name__ == "__main__":
    main()
