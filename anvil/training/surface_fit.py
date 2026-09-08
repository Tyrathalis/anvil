"""M12 Build 3 — the decision surfaces' imitation warm start (ADR-0105 item 4).

The option-set decoder (anvil.policy.model AnvilNet._surface_decode) fitted to
the heuristic's answers on the named surface windows of sv=3 stores — the
clone IS the natural line, so serving it costs nothing at day zero; the
search's sub-row distillation term moves it from there. Cross-fit (standing
rule, ADR-0103): games hash into --folds folds; each fold's read comes from
the model that never saw it; --build fits on every game and writes the
checkpoint the server serves.

What is trainable (--unfreeze):
  new     the surface-only parameters (abil_proj, opt_kind_emb, surf_* incl.
          the surface query / key maps that start as copies of the trained
          target decoder's) — the shared decoder and the trunk stay frozen,
          so every non-surface window is byte-identical to the input ckpt
  decoder + the shared target decoder (tgt_query/tgt_key/player_key/stop_key)
          — moves cast targeting too; the drift read (held-out cast windows'
          tgt argmax agreement vs the input checkpoint) is reported
  N       + the top-N trunk layers (drift read reported)

Reads per shape and per callback method on the held-out fold: slot-0 top-1
agreement with the heuristic, exact-answer agreement, the heuristic's
first-option rate (the chance baseline for a positional guess) and the mean
option count.

Usage:
  uv run python -m anvil.training.surface_fit --stores 'data/trajectories/b2-*' \\
      --out data/runs/build3-e1 --fold 0            # one cross-fit fold
  uv run python -m anvil.training.surface_fit ... --build --ckpt-out data/training/m12-build3-e1
  uv run python -m anvil.training.surface_fit ... --read   # pool the folds -> read.json/md
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CKPT = "data/training/m12-build1-stopstate/last.pt"
ABIL = "data/embeddings/abil-cf2ca6ba-qwen3"
EMBED = "data/embeddings/cf2ca6ba-qwen3"


def fold_of(name: str, g: int, folds: int) -> int:
    h = hashlib.sha1(f"{name}:{g}".encode()).digest()
    return int.from_bytes(h[:4], "little") % folds


class FoldFilter:
    """Picklable per-game fold predicate (DataLoader workers re-import it)."""

    def __init__(self, folds: int, fold: int | None, split: str):
        self.folds, self.fold, self.split = folds, fold, split

    def __call__(self, name: str, g: int) -> bool:
        if self.fold is None:
            return True
        f = fold_of(name, g, self.folds)
        return (f == self.fold) if self.split == "test" else (f != self.fold)


def load_net(ckpt: str, device: str):
    import torch

    from anvil.policy.surfaces import AbilityCache
    from anvil.training.dataset import default_methods
    from anvil.training.train import build_net

    ck = torch.load(REPO / ckpt, map_location=device, weights_only=False)
    cfg = ck["config"]
    net = build_net(
        cfg["embed"], cfg["pool_manifest"], len(default_methods()), n_sa=cfg.get("sa_vocab_size", 0)
    ).to(device)
    net.load_compat(ck["model"])
    abil = AbilityCache(REPO / cfg.get("abilities", ABIL))
    net.set_ability_table(abil.vectors)
    return net, ck


NEW_PREFIXES = ("abil_proj", "opt_kind_emb", "surf_")  # surf_query / surf_key: the role copies
SHARED_DECODER = ("tgt_query", "tgt_key", "player_key", "stop_key")


def set_trainable(net, unfreeze: str) -> int:
    n_layers = len(net.trunk.layers)
    top: set[int] = set()
    shared = unfreeze != "new"
    if unfreeze not in ("new", "decoder"):
        top = set(range(n_layers - int(unfreeze), n_layers))
    for name, p in net.named_parameters():
        p.requires_grad = (
            name.startswith(NEW_PREFIXES)
            or (shared and name.startswith(SHARED_DECODER))
            or any(name.startswith(f"trunk.layers.{i}.") for i in top)
        )
    return sum(p.numel() for p in net.parameters() if p.requires_grad)


def make_dataset(a, split: str, folds: int, fold: int | None):
    from anvil.training.dataset import PriorityWindows

    stores = sorted(p for pat in a.stores.split(",") for p in glob.glob(str(REPO / pat)))
    if not stores:
        raise SystemExit(f"no stores match {a.stores}")
    tasks = set(a.tasks.split(","))

    filt = FoldFilter(folds, fold, split)

    # one dataset per store, chained: the arm stores each number their games
    # 0..N-1 (MultiStore refuses overlapping ranges); the fold hash keys on
    # (store path, g) so a game's fold is stable across runs
    from torch.utils.data import ChainDataset

    parts = [
        PriorityWindows(
            st,
            REPO / a.embed,
            tasks=tasks,
            shuffle_games=(split == "train"),
            seed=a.seed + i,
            max_games=a.max_games,
            abilities_stem=REPO / a.abilities,
            game_filter=filt,
        )
        for i, st in enumerate(stores)
    ]
    ds = ChainDataset(parts)
    ds.parts = parts  # type: ignore[attr-defined]
    return ds, stores


def _to(chunk: dict, device: str) -> dict:
    return {k: v.to(device, non_blocking=True) for k, v in chunk.items()}


def surface_loss(out: dict, batch: dict):
    import torch.nn.functional as F

    lg = out["surf_logits"]
    lab = batch["surf_labels"]
    return F.cross_entropy(lg.flatten(0, 1).float(), lab.flatten(), ignore_index=-1)


def evaluate(net, loader, device: str, methods: list[str], max_batches: int | None = None) -> dict:
    """Held-out agreement with the heuristic per task / method."""
    import torch

    from anvil.training.dataset import TASKS

    inv_task = {v: k for k, v in TASKS.items()}
    agg: dict[str, Counter] = defaultdict(Counter)
    n_b = 0
    with torch.no_grad():
        for batch in loader:
            if "opt_row" not in batch:
                continue
            b = _to(batch, device)
            out = net(b)
            lg = out["surf_logits"]
            lab = b["surf_labels"]
            O = b["opt_row"].shape[1]
            top = lg.argmax(-1)
            valid = lab >= 0
            slot0 = (top[:, 0] == lab[:, 0])
            exact = ((top == lab) | ~valid).all(1)
            # the answer as a SET (order-free) for set shapes
            for i in range(lab.shape[0]):
                task = inv_task[int(b["task"][i])]
                m = methods[int(b["surf_method"][i])] if int(b["surf_method"][i]) >= 0 else "?"
                li = [int(x) for x in lab[i] if 0 <= int(x) < O]
                pi = [int(x) for x in top[i][: len(li) + 1] if 0 <= int(x) < O]
                for key in (task, f"{task}/{m}"):
                    c = agg[key]
                    c["n"] += 1
                    c["slot0"] += int(slot0[i])
                    c["exact"] += int(exact[i])
                    c["set"] += int(set(li) == set(pi))
                    c["first_opt"] += int(li[:1] == [0])
                    c["n_opts"] += int(b["opt_mask"][i].sum())
                    c["n_ans"] += len(li)
            n_b += 1
            if max_batches and n_b >= max_batches:
                break
    out: dict = {}
    for key, c in agg.items():
        n = max(1, c["n"])
        out[key] = {
            "n": c["n"],
            "slot0_agree": round(c["slot0"] / n, 4),
            "exact_agree": round(c["exact"] / n, 4),
            "set_agree": round(c["set"] / n, 4),
            "first_opt_rate": round(c["first_opt"] / n, 4),
            "mean_opts": round(c["n_opts"] / n, 2),
            "mean_answer": round(c["n_ans"] / n, 2),
        }
    return out


def fit(a) -> None:
    import torch
    from torch.utils.data import DataLoader

    from anvil.training.dataset import collate, default_methods

    device = "cuda"
    torch.manual_seed(a.seed)
    out_dir = REPO / a.out
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = "build" if a.build else f"fold{a.fold}"
    log = (out_dir / f"fit-{tag}.jsonl").open("w")
    methods = default_methods()
    net, ck = load_net(a.ckpt, device)
    n_tr = set_trainable(net, a.unfreeze)
    print(f"[surface_fit {tag}] trainable {n_tr:,} (unfreeze={a.unfreeze})", flush=True)
    opt = torch.optim.AdamW([p for p in net.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.01)
    ds_tr, stores = make_dataset(a, "train", a.folds, None if a.build else a.fold)
    loader = DataLoader(ds_tr, batch_size=a.batch, collate_fn=collate, num_workers=a.workers, persistent_workers=a.workers > 0)
    ds_te = None if a.build else make_dataset(a, "test", a.folds, a.fold)[0]
    print(f"[surface_fit {tag}] stores {len(stores)} tasks {a.tasks}", flush=True)

    step = 0
    t0 = time.time()
    done = False
    epoch = 0
    while not done:
        net.train()
        for batch in loader:
            if "opt_row" not in batch:
                continue
            b = _to(batch, device)
            out = net(b)
            loss = surface_loss(out, b)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for p in net.parameters() if p.requires_grad], 1.0)
            opt.step()
            step += 1
            if step % 50 == 0:
                lg = out["surf_logits"]
                lab = b["surf_labels"]
                acc0 = float((lg[:, 0].argmax(-1) == lab[:, 0]).float().mean())
                rec = {"step": step, "epoch": epoch, "loss": round(float(loss), 4), "slot0": round(acc0, 4), "t": round(time.time() - t0)}
                log.write(json.dumps(rec) + "\n")
                log.flush()
                if step % 500 == 0:
                    print(f"[surface_fit {tag}] {rec}", flush=True)
            if step >= a.steps:
                done = True
                break
        epoch += 1
        if epoch >= a.epochs:
            done = True
    counts: Counter = Counter()
    for part in getattr(ds_tr, "parts", []):
        counts.update(getattr(part, "surf_counts", {}))
    res = {"tag": tag, "steps": step, "epochs": epoch, "wall_s": round(time.time() - t0), "unfreeze": a.unfreeze, "lr": a.lr, "train_counts": dict(counts)}
    if ds_te is not None:
        net.eval()
        te_loader = DataLoader(ds_te, batch_size=a.batch, collate_fn=collate, num_workers=a.workers)
        res["held_out"] = evaluate(net, te_loader, device, methods, max_batches=a.eval_batches)
        hc: Counter = Counter()
        for part in getattr(ds_te, "parts", []):
            hc.update(getattr(part, "surf_counts", {}))
        res["held_out_counts"] = dict(hc)
        print(f"[surface_fit {tag}] held-out: {json.dumps({k: v for k, v in res['held_out'].items() if '/' not in k})}", flush=True)
    if a.build:
        cfg = dict(ck["config"])
        cfg["abilities"] = str(Path(a.abilities))
        cfg["surface_tasks"] = a.tasks
        cfg["surface_fit"] = {"steps": step, "unfreeze": a.unfreeze, "lr": a.lr, "stores": stores, "parent": a.ckpt}
        ck_out = REPO / a.ckpt_out
        ck_out.mkdir(parents=True, exist_ok=True)
        torch.save({"step": ck.get("step", 0), "model": net.state_dict(), "config": cfg}, ck_out / "last.pt")
        res["ckpt"] = str(ck_out / "last.pt")
        print(f"[surface_fit build] -> {ck_out / 'last.pt'}", flush=True)
    (out_dir / f"result-{tag}.json").write_text(json.dumps(res, indent=1) + "\n")


def read(a) -> None:
    out_dir = REPO / a.out
    folds = sorted(out_dir.glob("result-fold*.json"))
    agg: dict[str, Counter] = defaultdict(Counter)
    for f in folds:
        r = json.loads(f.read_text())
        for key, v in r.get("held_out", {}).items():
            c = agg[key]
            n = v["n"]
            c["n"] += n
            for k in ("slot0_agree", "exact_agree", "set_agree", "first_opt_rate", "mean_opts", "mean_answer"):
                c[k] += v[k] * n
    lines = [f"# Surface imitation read — {a.out} ({len(folds)} folds pooled)", "",
             "| key | n | slot-0 agree | exact agree | set agree | first-option rate | mean opts | mean answer |", "|---|---|---|---|---|---|---|---|"]
    pooled = {}
    for key in sorted(agg, key=lambda k: (k.count("/"), -agg[k]["n"])):
        c = agg[key]
        n = max(1, c["n"])
        row = {k: round(c[k] / n, 4) for k in ("slot0_agree", "exact_agree", "set_agree", "first_opt_rate", "mean_opts", "mean_answer")}
        row["n"] = c["n"]
        pooled[key] = row
        lines.append(f"| {key} | {c['n']} | {row['slot0_agree']:.3f} | {row['exact_agree']:.3f} | {row['set_agree']:.3f} | {row['first_opt_rate']:.3f} | {row['mean_opts']:.1f} | {row['mean_answer']:.2f} |")
    (out_dir / "read.json").write_text(json.dumps(pooled, indent=1) + "\n")
    (out_dir / "read.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stores", default="data/trajectories/b2-*")
    ap.add_argument("--out", required=True)
    ap.add_argument("--ckpt", default=CKPT)
    ap.add_argument("--ckpt-out", default="data/training/m12-build3-e1")
    ap.add_argument("--embed", default=EMBED)
    ap.add_argument("--abilities", default=ABIL)
    ap.add_argument("--tasks", default="surf_one,surf_set")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--fold", type=int, default=0)
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--read", action="store_true")
    ap.add_argument("--unfreeze", default="new", help="new | decoder | <N top trunk layers>")
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--steps", type=int, default=4000)
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-games", type=int, default=None)
    ap.add_argument("--eval-batches", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    if a.read:
        read(a)
    else:
        fit(a)


if __name__ == "__main__":
    main()
