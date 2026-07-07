"""BC training loop (M1 D5). uv run python -m anvil.training.train ...

Metrics discipline (m1-bc-plan D7, ADR-0005): the headline eval number is
agreement EXCLUDING single-legal-option windows (candidate basis: pass-only
windows are the forced ones), with raw and pass-excluded agreement reported
alongside. Every eval row lands in metrics.jsonl; checkpoints carry the full
config + data pins.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from anvil.encoder.cards import CardEncoder
from anvil.encoder.cardtext import pool_features
from anvil.encoder.transform import (ENTITY_FEATURES, GLOBAL_FEATURES, HISTORY_K,
                                     PLAYER_FEATURES, TRANSFORM_VERSION)
from anvil.policy.model import AnvilNet
from anvil.training.dataset import PriorityWindows, collate, default_methods

REPO = Path(__file__).parents[1]


def build_net(embedding_stem: str, pool_manifest: str, n_methods: int) -> AnvilNet:
    m = json.loads(Path(pool_manifest).read_text())
    meta = json.loads(Path(f"{embedding_stem}.json").read_text())
    feats = torch.from_numpy(pool_features(m, meta["names"]))
    return AnvilNet(CardEncoder(embedding_stem, feats),
                    n_entity_features=len(ENTITY_FEATURES),
                    n_global=len(GLOBAL_FEATURES), n_players=2,
                    n_player_features=len(PLAYER_FEATURES),
                    n_methods=n_methods, history_k=HISTORY_K)


@torch.no_grad()
def evaluate(net: AnvilNet, loader: DataLoader, device: str, max_batches: int) -> dict:
    net.eval()
    agree = raw = 0
    n_honest = n_raw = 0
    agree_np = n_np = 0
    tgt_ok = tgt_n = 0
    x_ok = x_n = 0
    vsum = vn = 0.0
    for i, batch in enumerate(loader):
        if i >= max_batches:
            break
        batch = {k: v.to(device) for k, v in batch.items()}
        with torch.autocast(device, dtype=torch.bfloat16):
            out = net(batch)
        pred = out["policy_logits"].argmax(1)
        ok = pred == batch["label"]
        multi = batch["cand_mask"].sum(1) > 1  # single-legal-option exclusion
        raw += ok.sum().item()
        n_raw += ok.numel()
        agree += (ok & multi).sum().item()
        n_honest += multi.sum().item()
        nonpass = batch["label"] > 0
        agree_np += (ok & nonpass).sum().item()
        n_np += nonpass.sum().item()
        tm = batch["tgt_labels"] >= 0
        tgt_ok += ((out["tgt_logits"].argmax(-1) == batch["tgt_labels"]) & tm).sum().item()
        tgt_n += tm.sum().item()
        xm = batch["x_val"] >= 0
        x_ok += (out["x_logits"].argmax(-1)[xm] == batch["x_val"][xm]).sum().item()
        x_n += xm.sum().item()
        vm = batch["has_outcome"].bool()
        if vm.any():
            vsum += torch.nn.functional.binary_cross_entropy_with_logits(
                out["value_logit"][vm], batch["won"][vm].float(), reduction="sum").item()
            vn += vm.sum().item()
    net.train()
    # per-metric ns alongside every rate: the D5 matrix compares runs, and a
    # rate without its sample size hides the noise floor (nonpass at n~1.4K
    # has SE ~1.2% — arms closer than that are indistinguishable)
    return {
        "agree_honest": agree / max(n_honest, 1),   # THE number (forced excluded)
        "agree_raw": raw / max(n_raw, 1),
        "agree_nonpass": agree_np / max(n_np, 1),
        "acc_target": tgt_ok / max(tgt_n, 1),
        "acc_x": x_ok / max(x_n, 1),
        "value_bce": vsum / max(vn, 1),
        "eval_windows": n_raw,
        "n_honest": n_honest, "n_nonpass": n_np, "n_target": tgt_n,
        "n_x": x_n, "n_value": int(vn),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="data/trajectories/d3pilot-20260704-175219")
    ap.add_argument("--embed", default="data/embeddings/cf2ca6ba-qwen3")
    ap.add_argument("--pool-manifest", default="data/pool/pool-cf2ca6ba.json")
    ap.add_argument("--out", default=None)
    # 512 OOMs on a 24GB card sharing with the desktop: big-board windows hit
    # 150+ entity tokens and attention memory is quadratic in sequence length
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--warmup", type=int, default=500)
    ap.add_argument("--steps", type=int, default=20000)
    ap.add_argument("--pass-weight", type=float, default=0.3)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-games", type=int, default=None, help="train-subset cap (learning curves)")
    ap.add_argument("--eval-every", type=int, default=1000)
    ap.add_argument("--eval-batches", type=int, default=60)
    # mid-run evals stay cheap (trajectory shape); the final eval is the number
    # runs get compared on. 600 batches ~ 154K windows -> nonpass SE ~0.33%,
    # X-head n in the hundreds; resolves ~1% arm differences in the D5 matrix
    ap.add_argument("--final-eval-batches", type=int, default=600)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    torch.manual_seed(a.seed)
    device = "cuda"
    out_dir = Path(a.out or f"data/training/run-{_dt.datetime.now():%Y%m%d-%H%M%S}")
    out_dir.mkdir(parents=True, exist_ok=True)

    methods = default_methods()
    net = build_net(a.embed, a.pool_manifest, len(methods)).to(device)
    n_params = sum(p.numel() for p in net.parameters() if p.requires_grad)

    train_ds = PriorityWindows(a.store, a.embed, methods, split="train",
                               seed=a.seed, max_games=a.max_games)
    val_ds = PriorityWindows(a.store, a.embed, methods, split="val",
                             shuffle_games=False)
    vp_ds = PriorityWindows(a.store, a.embed, methods, split="valpair",
                            shuffle_games=False)
    train = DataLoader(train_ds, batch_size=a.batch, collate_fn=collate,
                       num_workers=a.workers, persistent_workers=True,
                       prefetch_factor=4)
    val = DataLoader(val_ds, batch_size=a.batch, collate_fn=collate, num_workers=4)
    vp = DataLoader(vp_ds, batch_size=a.batch, collate_fn=collate, num_workers=4)

    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=0.01)

    def lr_at(step: int) -> float:
        if step < a.warmup:
            return a.lr * step / a.warmup
        t = (step - a.warmup) / max(a.steps - a.warmup, 1)
        return a.lr * 0.5 * (1 + math.cos(math.pi * min(t, 1.0)))

    config = {**vars(a), "params": n_params, "methods_version": 1,
              "transform_version": TRANSFORM_VERSION,
              "embed_meta": json.loads(Path(f"{a.embed}.json").read_text())}
    del config["out"]
    (out_dir / "config.json").write_text(json.dumps(config, indent=1, default=str) + "\n")
    metrics = open(out_dir / "metrics.jsonl", "a")
    print(f"[train] {n_params/1e6:.1f}M params -> {out_dir}")

    step = 0
    t0 = time.time()
    win_seen = 0
    while step < a.steps:
        for batch in train:
            if step >= a.steps:
                break
            for g in opt.param_groups:
                g["lr"] = lr_at(step)
            batch = {k: v.to(device, non_blocking=True) for k, v in batch.items()}
            with torch.autocast(device, dtype=torch.bfloat16):
                L = net.losses(batch, pass_weight=a.pass_weight)
            opt.zero_grad(set_to_none=True)
            L["loss"].backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            win_seen += batch["label"].shape[0]
            step += 1

            if step % 100 == 0:
                row = {"step": step,
                       **{k: float(L[k].detach()) for k in
                          ("loss", "policy", "target", "x", "value")},
                       "lr": lr_at(step),
                       "windows": win_seen, "wall_s": round(time.time() - t0, 1)}
                metrics.write(json.dumps(row) + "\n")
                metrics.flush()
                if step % 500 == 0:
                    print(f"[train] step {step}: loss {row['loss']:.3f} "
                          f"({win_seen / (time.time() - t0):.0f} win/s)")
            if step % a.eval_every == 0 or step == a.steps:
                nb = a.final_eval_batches if step == a.steps else a.eval_batches
                ev = {"step": step, "split": "val", **evaluate(net, val, device, nb)}
                ep = {"step": step, "split": "valpair", **evaluate(net, vp, device, nb)}
                for row in (ev, ep):
                    metrics.write(json.dumps(row) + "\n")
                metrics.flush()
                print(f"[eval] step {step}: honest {ev['agree_honest']:.4f} "
                      f"raw {ev['agree_raw']:.4f} nonpass {ev['agree_nonpass']:.4f} "
                      f"tgt {ev['acc_target']:.4f} | valpair honest {ep['agree_honest']:.4f}")
                torch.save({"step": step, "model": net.state_dict(), "config": config},
                           out_dir / "last.pt")
    print(f"[train] done: {step} steps, {win_seen} windows, "
          f"{(time.time() - t0) / 3600:.2f}h")


if __name__ == "__main__":
    main()
