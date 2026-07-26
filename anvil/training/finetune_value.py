"""Value-head-only fine-tune on corrected outcome labels (M2 D4).

Background (2026-07-11): the obs end-record's winner field was derived from
the post-elimination live player list in the fork — ~always 0, wrong for
~50% of games — so every value head through d2-sa trained on seat noise
(d2-sa value head vs TRUE outcomes: AUC 0.506 = chance). The loader now
joins the true winner from games.jsonl (TrajectoryStore.winner_seat).

This script is the cheap re-baseline: load a checkpoint, freeze everything
except the value-head MLP, train on corrected labels. Because only
value_head changes, the policy/target/X heads — the RL init — are untouched
by construction; the result measures how much outcome signal the (policy-
trained) trunk already carries. The full-visibility asymmetric critic (D4
proper) is the next rung; this number is its lower baseline.

  uv run python -m anvil.training.finetune_value \\
      --ckpt data/training/d2-sa/last.pt --out data/training/d4-valuefix

M2 D4 second rung — the full-visibility asymmetric critic (design §4):
`--full-vis --trainable all` trains the whole net as a critic tower on
full-visibility windows (opponent hands visible; the info-set gate bypassed
— critic instrument only, never a policy input). Init from the BC
checkpoint (warm board-reading trunk); the resulting checkpoint is a CRITIC,
its policy heads are off-distribution garbage — never serve from it.

  uv run python -m anvil.training.finetune_value \\
      --ckpt data/training/d2-sa/last.pt --full-vis --trainable all \\
      --lr 1e-4 --steps 100000 --out data/training/d4-critic-fullvis
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from anvil.training.dataset import PriorityWindows, collate, default_methods
from anvil.training.train import build_net


def _auc(scores: np.ndarray, labels: np.ndarray) -> float:
    pos = labels == 1
    n1, n0 = int(pos.sum()), int((~pos).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = np.empty(len(scores))
    r[np.argsort(scores, kind="stable")] = np.arange(1, len(scores) + 1)
    return float((r[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def _train_batch(net, batch: dict, device: str, denom: int) -> float:
    """Forward+backward one training batch; returns the mean loss value.

    VRAM elasticity (task #12): on CUDA OOM the batch is split in half
    along the batch dim and gradient-ACCUMULATED — each half contributes
    its sum-loss / denom, so the accumulated gradient equals the whole
    batch's mean-BCE gradient and the effective batch size (a training
    hyperparameter, unlike rl.py's seg) is preserved exactly."""
    b = next(iter(batch.values())).shape[0]
    try:
        with torch.autocast(device, dtype=torch.bfloat16):
            out = net(batch)
            m = batch["has_outcome"].bool()
            if not m.any():
                return 0.0
            loss = torch.nn.functional.binary_cross_entropy_with_logits(
                out["value_logit"][m], batch["won"][m].float(),
                reduction="sum") / denom
        loss.backward()
        return float(loss.detach())
    except torch.cuda.OutOfMemoryError:
        if b < 2:
            raise  # not a batching problem at one example
        torch.cuda.empty_cache()
        print(f"[vfix] OOM at batch {b} -> gradient-accumulating halves")
        h = b // 2
        return (_train_batch(net, {k: v[:h] for k, v in batch.items()},
                             device, denom)
                + _train_batch(net, {k: v[h:] for k, v in batch.items()},
                               device, denom))


@torch.no_grad()
def eval_value(net, loader, device: str, max_batches: int) -> dict:
    net.eval()
    probs, wons = [], []
    for i, batch in enumerate(loader):
        if i >= max_batches:
            break
        batch = {k: v.to(device) for k, v in batch.items()}
        with torch.autocast(device, dtype=torch.bfloat16):
            out = net(batch)
        m = batch["has_outcome"].bool()
        if m.any():
            probs.append(torch.sigmoid(out["value_logit"][m].float()).cpu().numpy())
            wons.append(batch["won"][m].cpu().numpy())
    p = np.concatenate(probs)
    y = np.concatenate(wons).astype(np.float64)
    eps = 1e-7
    pc = np.clip(p, eps, 1 - eps)
    return {"value_bce": float(-(y * np.log(pc) + (1 - y) * np.log(1 - pc)).mean()),
            "value_auc": _auc(p, y), "n_value": int(len(y)),
            "pred_std": float(p.std())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="data/training/d2-sa/last.pt")
    ap.add_argument("--store", default=None, help="default: the ckpt's corpus")
    ap.add_argument("--out", default=None)
    ap.add_argument("--steps", type=int, default=20000)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--warmup", type=int, default=200)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--eval-every", type=int, default=2000)
    ap.add_argument("--eval-batches", type=int, default=100)
    ap.add_argument("--final-eval-batches", type=int, default=600)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--full-vis", action="store_true",
                    help="asymmetric-critic windows (design §4): all entity "
                         "identities visible; critic instrument, never policy input")
    ap.add_argument("--trainable", default="value_head", choices=["value_head", "all"],
                    help="value_head = frozen-trunk probe; all = critic tower "
                         "(policy heads in the output ckpt become garbage — never serve)")
    a = ap.parse_args()

    torch.manual_seed(a.seed)
    device = "cuda"
    ck = torch.load(a.ckpt, map_location="cpu", weights_only=False)
    cfg = ck["config"]
    store = a.store or cfg["store"]
    out_dir = Path(a.out or f"data/training/valuefix-{_dt.datetime.now():%Y%m%d-%H%M%S}")
    out_dir.mkdir(parents=True, exist_ok=True)

    methods = default_methods()
    net = build_net(cfg["embed"], cfg["pool_manifest"], len(methods),
                    n_sa=cfg.get("sa_vocab_size", 0)).to(device)
    net.load_compat(ck["model"])
    for name, p in net.named_parameters():
        p.requires_grad = a.trainable == "all" or name.startswith("value_head")
    n_train = sum(p.numel() for p in net.parameters() if p.requires_grad)

    train_ds = PriorityWindows(store, cfg["embed"], methods, split="train",
                               seed=a.seed, full_vis=a.full_vis)
    val_ds = PriorityWindows(store, cfg["embed"], methods, split="val",
                             shuffle_games=False, full_vis=a.full_vis)
    train = DataLoader(train_ds, batch_size=a.batch, collate_fn=collate,
                       num_workers=a.workers, persistent_workers=True, prefetch_factor=4)
    val = DataLoader(val_ds, batch_size=a.batch, collate_fn=collate, num_workers=4)

    opt = torch.optim.AdamW([p for p in net.parameters() if p.requires_grad],
                            lr=a.lr, weight_decay=0.01)

    def lr_at(step: int) -> float:
        if step < a.warmup:
            return a.lr * step / a.warmup
        t = (step - a.warmup) / max(a.steps - a.warmup, 1)
        return a.lr * 0.5 * (1 + math.cos(math.pi * min(t, 1.0)))

    config = {**cfg, "value_finetune": {**vars(a), "base_step": ck.get("step"),
                                        "trainable_params": n_train,
                                        "label_fix": "winner_seat join (2026-07-11)"}}
    (out_dir / "config.json").write_text(json.dumps(config, indent=1, default=str) + "\n")
    metrics = open(out_dir / "metrics.jsonl", "a")

    base = eval_value(net, val, device, a.eval_batches)
    print(f"[vfix] baseline (broken-label head vs TRUE labels): "
          f"bce {base['value_bce']:.4f} auc {base['value_auc']:.4f} "
          f"(n={base['n_value']}, pred_std {base['pred_std']:.4f})")
    metrics.write(json.dumps({"step": 0, "split": "val", **base}) + "\n")
    metrics.flush()

    step, t0, seen = 0, time.time(), 0
    while step < a.steps:
        for batch in train:
            if step >= a.steps:
                break
            for g in opt.param_groups:
                g["lr"] = lr_at(step)
            net.train()
            batch = {k: v.to(device, non_blocking=True) for k, v in batch.items()}
            n_out = int(batch["has_outcome"].sum())
            if n_out == 0:
                continue
            opt.zero_grad(set_to_none=True)
            loss_val = _train_batch(net, batch, device, n_out)
            opt.step()
            seen += n_out
            step += 1
            if step % 200 == 0:
                metrics.write(json.dumps({"step": step, "value_loss": loss_val,
                                          "lr": lr_at(step), "windows": seen,
                                          "wall_s": round(time.time() - t0, 1)}) + "\n")
                metrics.flush()
            if step % 1000 == 0:
                print(f"[vfix] step {step}: loss {loss_val:.4f} "
                      f"({seen / (time.time() - t0):.0f} win/s)")
            if step % a.eval_every == 0 or step == a.steps:
                nb = a.final_eval_batches if step == a.steps else a.eval_batches
                ev = eval_value(net, val, device, nb)
                metrics.write(json.dumps({"step": step, "split": "val", **ev}) + "\n")
                metrics.flush()
                print(f"[vfix] eval step {step}: bce {ev['value_bce']:.4f} "
                      f"auc {ev['value_auc']:.4f} pred_std {ev['pred_std']:.4f}")
                torch.save({"step": step, "model": net.state_dict(), "config": config},
                           out_dir / "last.pt")
    print(f"[vfix] done: {step} steps, {seen} outcome windows, "
          f"{(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
