"""The target decoder's player-position refit (09-21, ADR-0116).

The cast-target decoder was trained on a mixed label: the registered seat index
copied into a self-first row (from seat 1 the "opponent" label pointed at the
self row). A checkpoint trained that way never learned player identity — it
served a 46% self-target rate against the heuristic's 11% on b4post — and the
corrected decode alone cannot repair it. This refit retrains ONLY the target
decoder's parameters (tgt_query, tgt_key, player_key, stop_key, slot_emb) on
heuristic-labeled windows under the corrected labels, the trunk and every other
head frozen, so the served build stays byte-identical everywhere but the
target head. The examples are collected once from the stores (windows with a
player target, plus an equal number of other targeted casts so the entity part
does not drift), held out by a running 1-in-5, and the report gives per-class
accuracy before / after (entity, player-self, player-opp, STOP) and the
predicted-class mix on player slots.

Usage: uv run python -m anvil.training.target_refit --ckpt data/training/m12-build4-e1a/last.pt \\
         --store <dir>[,<dir>] --out data/training/m12-build4-e1a-tgt [--n-player 3000] [--epochs 6]
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from anvil.encoder.transform import PLAYER_TARGET_CONVENTION
from anvil.training.dataset import PriorityWindows, collate, default_methods, default_sa_vocab
from anvil.training.train import build_net

HEAD_PARAMS = ("tgt_query.", "tgt_key.", "player_key.", "stop_key", "slot_emb")


def _to(batch: dict, dev) -> dict:
    return {k: (v.to(dev) if hasattr(v, "to") else v) for k, v in batch.items()}


def _classes(batch: dict) -> tuple[torch.Tensor, int, int]:
    """Per-slot class of the label: 0 entity, 1 player-self, 2 player-opp, 3 STOP, -1 none."""
    n = batch["ent_mask"].shape[1]
    p = batch["players"].shape[1]
    lab = batch["tgt_labels"]
    cls = torch.full_like(lab, -1)
    cls[(lab >= 0) & (lab < n)] = 0
    cls[lab == n] = 1
    cls[(lab > n) & (lab < n + p)] = 2
    cls[lab == n + p] = 3
    return cls, n, p


def _pred_class(pred: torch.Tensor, n: int, p: int) -> torch.Tensor:
    cls = torch.zeros_like(pred)
    cls[pred == n] = 1
    cls[(pred > n) & (pred < n + p)] = 2
    cls[pred == n + p] = 3
    return cls


def _first(x):
    return x[0]


class TolerantWindows(PriorityWindows):
    """PriorityWindows that SKIPS a game whose frame fails the loader's data
    guards (the ADR-0005 superset check tripped on one b2-heurarm game) instead
    of killing the collection — a refit reads what is clean and counts the rest."""

    def __iter__(self):
        from anvil.store.trajectories import open_store

        store = open_store(self.store_dir)
        for g in self._epoch_games(store):
            try:
                yield from self._examples(store, g)
            except Exception as e:  # noqa: BLE001
                print(f"[refit] skipping game {g}: {str(e)[:90]}", flush=True)
                continue


def collect(stores: str, embed: str, n_player: int, workers: int, seed: int, max_batches: int):
    """One store at a time (arm stores share game indices, which MultiStore
    refuses); the counters carry across stores."""
    player, other = [], []
    rng = random.Random(seed)
    t0 = time.time()
    scanned = 0
    for store in stores.split(","):
        ds = TolerantWindows(store, embed, default_methods(), split=None, seed=seed,
                             tasks={"priority"}, sa_vocab=default_sa_vocab())
        dl = DataLoader(ds, batch_size=1, collate_fn=_first, num_workers=workers, prefetch_factor=8)
        for ex in dl:
            scanned += 1
            tk = ex["tgt_kind"]
            if (tk == 1).any():
                player.append(ex)
            elif (tk >= 0).any() and rng.random() < 0.02:
                other.append(ex)
            if scanned % 50000 == 0:
                print(f"[refit] scanned {scanned} windows: {len(player)} player-target, {len(other)} other "
                      f"({time.time() - t0:.0f} s)", flush=True)
            if len(player) >= n_player or scanned >= max_batches:
                break
        if len(player) >= n_player or scanned >= max_batches:
            break
    other = other[: len(player)]
    print(f"[refit] collected {len(player)} player-target + {len(other)} other targeted windows "
          f"from {scanned} scanned in {time.time() - t0:.0f} s", flush=True)
    return player, other


@torch.no_grad()
def evaluate(net, examples: list, dev, batch: int) -> dict:
    net.eval()
    ok = torch.zeros(4)
    n = torch.zeros(4)
    mix = torch.zeros(4)  # predicted class on player-labelled slots
    for i in range(0, len(examples), batch):
        b = _to(collate(examples[i:i + batch]), dev)
        out = net(b)
        cls, ne, p = _classes(b)
        pred = out["tgt_logits"].argmax(-1)
        for c in range(4):
            m = cls == c
            n[c] += m.sum().item()
            ok[c] += ((pred == b["tgt_labels"]) & m).sum().item()
        pm = (cls == 1) | (cls == 2)
        pc = _pred_class(pred[pm], ne, p)
        for c in range(4):
            mix[c] += (pc == c).sum().item()
    names = ["entity", "player_self", "player_opp", "stop"]
    acc = {names[c]: (round((ok[c] / max(n[c], 1)).item(), 4), int(n[c])) for c in range(4)}
    tot = max(mix.sum().item(), 1)
    return {"acc": acc, "pred_mix_on_player_slots": {names[c]: round(mix[c].item() / tot, 4) for c in range(4)}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--store", required=True, help="heuristic-labelled sv=3 store dir(s), comma list")
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-player", type=int, default=3000)
    ap.add_argument("--max-scan", type=int, default=3_000_000)
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--player-weight", type=float, default=4.0)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args()
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    ck = torch.load(a.ckpt, map_location="cpu", weights_only=False)
    cfg = dict(ck["config"])
    methods = default_methods()
    net = build_net(cfg["embed"], cfg["pool_manifest"], len(methods), n_sa=cfg.get("sa_vocab_size", 0)).to(a.device)
    net.load_compat(ck["model"])
    net.eval()  # the trunk's features stay deterministic; only the head trains
    for name, prm in net.named_parameters():
        prm.requires_grad = name.startswith(HEAD_PARAMS)
    head = [p for p in net.parameters() if p.requires_grad]
    print(f"[refit] head params {sum(p.numel() for p in head) / 1e6:.2f}M of "
          f"{sum(p.numel() for p in net.parameters()) / 1e6:.1f}M", flush=True)

    player, other = collect(a.store, cfg["embed"], a.n_player, a.workers, a.seed, a.max_scan)
    rng = random.Random(a.seed)
    allx = player + other
    rng.shuffle(allx)
    val = [x for i, x in enumerate(allx) if i % 5 == 0]
    train = [x for i, x in enumerate(allx) if i % 5 != 0]
    before = evaluate(net, val, a.device, a.batch)
    print(f"[refit] BEFORE: {json.dumps(before)}", flush=True)

    opt = torch.optim.AdamW(head, lr=a.lr, weight_decay=0.0)
    steps = 0
    for ep in range(a.epochs):
        rng.shuffle(train)
        tot = 0.0
        nb = 0
        for i in range(0, len(train), a.batch):
            b = _to(collate(train[i:i + a.batch]), a.device)
            out = net(b)
            lg = out["tgt_logits"]
            lab = b["tgt_labels"]
            cls, _, _ = _classes(b)
            w = torch.ones_like(lab, dtype=torch.float32)
            w[(cls == 1) | (cls == 2)] = a.player_weight
            ce = F.cross_entropy(lg.reshape(-1, lg.shape[-1]).float(), lab.reshape(-1).clamp(min=0),
                                 reduction="none").reshape(lab.shape)
            loss = (ce * w * (lab >= 0)).sum() / (w * (lab >= 0)).sum().clamp(min=1)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(head, 1.0)
            opt.step()
            tot += loss.item()
            nb += 1
            steps += 1
        ev = evaluate(net, val, a.device, a.batch)
        print(f"[refit] epoch {ep + 1}: loss {tot / max(nb, 1):.4f} val {json.dumps(ev['acc'])} "
              f"mix {json.dumps(ev['pred_mix_on_player_slots'])}", flush=True)
    after = evaluate(net, val, a.device, a.batch)
    cfg["player_target_convention"] = PLAYER_TARGET_CONVENTION
    cfg["target_refit"] = {"from": a.ckpt, "stores": a.store, "n_player": len(player), "n_other": len(other),
                           "epochs": a.epochs, "lr": a.lr, "player_weight": a.player_weight, "steps": steps,
                           "before": before, "after": after, "head_params": HEAD_PARAMS,
                           "date": time.strftime("%Y-%m-%d %H:%M")}
    torch.save({"step": ck.get("step", 0), "model": net.state_dict(), "config": cfg}, out_dir / "last.pt")
    (out_dir / "refit.json").write_text(json.dumps(cfg["target_refit"], indent=2))
    print(f"[refit] AFTER: {json.dumps(after)}\n[refit] saved {out_dir / 'last.pt'}", flush=True)


if __name__ == "__main__":
    main()
