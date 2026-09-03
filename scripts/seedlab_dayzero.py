"""Bank the day-zero seedlab decode CE for a checkpoint (ADR-0086).

With the own-emission dense decode term retired, the FUND gate's decode
leg reads the SEEDLAB CE (certified best-arm targets, seedlabels.py) —
so the day-zero value must be banked exactly at the init ckpt, not
approximated by the iteration-0 calibration read (which sits ~50
optimizer steps in; m10-probe1's read there was 2.730).

    uv run python scripts/seedlab_dayzero.py \
        --ckpt data/training/m10-sched-init/last.pt \
        --labels data/runs/sched-sweep-m10/seed-sched-labels.jsonl \
        --store data/trajectories/m10-ceiling-census-20260825-212414 \
        --out data/training/m10-sched-init/seedlab-dayzero.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--store", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--seg", type=int, default=128)
    ap.add_argument("--follow", action="store_true",
                    help="ADR-0092: bank the FOLLOW day-zero instead — feed-and-"
                    "follow CE on the priority pointer at certified windows "
                    "with the certified arm fed (build_follow_batch/follow_pass)")
    args = ap.parse_args()

    from anvil.bridge.featurize import Featurizer
    from anvil.training.dataset import default_methods
    from anvil.training.rl import make_forward_segments
    from anvil.training.seedlabels import build_seed_batch, seed_pass
    from anvil.training.train import build_net

    dev = args.device
    ckpt = torch.load(args.ckpt, map_location=dev, weights_only=False)
    cfg = ckpt["config"]
    methods = default_methods()
    net = build_net(
        cfg["embed"], cfg["pool_manifest"], len(methods),
        n_sa=cfg.get("sa_vocab_size", 0),
    ).to(dev)
    net.load_compat(ckpt["model"])
    net.eval()

    # ADR-0088: parallel comma-lists of (labels, store) pairs — the mint
    # spans stores whose game-index ranges collide, so each labels file
    # joins only its own store (the rl.py loader convention)
    feat = Featurizer(cfg["embed"], methods)
    if args.follow:
        from anvil.training.seedlabels import build_follow_batch, follow_pass

        build_seed_batch, seed_pass = build_follow_batch, follow_pass
    seedlab = None
    for lp, sp in zip(args.labels.split(","), args.store.split(","), strict=True):
        b = build_seed_batch(lp, sp, feat)
        if b is None:
            continue
        if seedlab is None:
            seedlab = b
        else:
            seedlab["segs"] += b["segs"]
            seedlab["n"] += b["n"]
            seedlab["miss"] += b["miss"]
            seedlab["unmatched"] += b["unmatched"]
    if seedlab is None:
        raise SystemExit("seed labels joined ZERO windows — nothing to bank")

    fwd_segs = make_forward_segments(dev, args.seg)
    ce = seed_pass(net, seedlab["segs"], fwd_segs, 0.0, grad=False)

    out = {
        ("follow_ce" if args.follow else "seedlab_ce"): round(ce, 6),
        "n_windows": seedlab["n"],
        "miss": seedlab["miss"],
        "unmatched": seedlab["unmatched"],
        "era": seedlab["era"],
        "ckpt": args.ckpt,
        "ckpt_step": ckpt.get("step"),
        "labels": args.labels,
        "store": args.store,
    }
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n")
    print(f"[seedlab-dayzero] {out}")


if __name__ == "__main__":
    main()
