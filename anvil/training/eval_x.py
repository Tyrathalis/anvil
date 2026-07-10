"""X-head eval at full-val power (ADR-0006 rare-label clause).

The 600-batch final eval sees ~173 X windows (SE ~4pp) — too coarse to decide
whether the X head has stopped improving with corpus size. This sweeps the
ENTIRE val split, keeps only windows with an X label (~600 in the pilot val),
and reports X accuracy per checkpoint at SE ~2pp.

  uv run python -m anvil.training.eval_x --ckpts a/last.pt b/last.pt ...
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from anvil.store.trajectories import open_store
from anvil.training.dataset import PriorityWindows, _split_of, collate, default_methods
from anvil.training.train import build_net


def x_windows(cfg: dict, max_games: int | None) -> list[dict]:
    ds = PriorityWindows(cfg["store"], cfg["embed"], default_methods(),
                         split="val", shuffle_games=False)
    store = open_store(cfg["store"])
    games = [g for g in store.game_indices() if _split_of(g) == "val"]
    if max_games:
        games = games[:max_games]
    wins = []
    for g in games:
        try:
            for ex in ds._examples(store, g):
                if int(ex["x_val"]) >= 0:
                    wins.append(ex)
        except Exception as e:
            if "did not decompress" not in str(e):
                raise
    return wins


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpts", nargs="+", required=True)
    ap.add_argument("--max-games", type=int, default=None)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--store", default=None,
                    help="override the ckpt's store spec (e.g. pilot-only for the "
                         "fixed 672-window basis the ADR-0006 curves used; the "
                         "split is a pure function of game index, so a store "
                         "subset reproduces its historical basis exactly)")
    a = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    wins = None
    for path in a.ckpts:
        ckpt = torch.load(path, map_location=device, weights_only=False)
        cfg = dict(ckpt["config"])
        if a.store:
            cfg["store"] = a.store
        if wins is None:  # same store/split across ckpts: collect once
            wins = x_windows(cfg, a.max_games)
            print(f"[eval_x] {len(wins)} X windows in the val split")
        net = build_net(cfg["embed"], cfg["pool_manifest"], len(default_methods())).to(device)
        net.load_state_dict(ckpt["model"])
        net.eval()
        ok = n = 0
        with torch.no_grad():
            for i in range(0, len(wins), a.batch):
                c = {k: v.to(device) for k, v in collate(wins[i:i + a.batch]).items()}
                with torch.autocast(device, dtype=torch.bfloat16):
                    out = net(c)
                m = c["x_val"] >= 0
                ok += (out["x_logits"].argmax(-1)[m] == c["x_val"][m]).sum().item()
                n += int(m.sum())
        se = (0.25 / n) ** 0.5
        print(f"[eval_x] {path}: X acc {ok / max(n, 1):.4f} (n={n}, SE ~{se:.3f})")


if __name__ == "__main__":
    main()
