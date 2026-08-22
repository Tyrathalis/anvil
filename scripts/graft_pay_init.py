"""Graft the M9 §3c payment params onto a pre-payment checkpoint (D4 recipe
pin 1, m9-plan).

Why this exists: the serve path gates the `mtg.pay_mana_class` tag on the
checkpoint actually carrying `pay_` params (`server.has_pay` — the
never-serve-fresh-init rule), and the self-play loop serves `--ckpt`
directly at iteration 0. Launching D4 straight from `d6-run11/iter-019`
would therefore bridge ZERO payment windows at iter-0: no live deviation
baseline, no `pay_class` examples in the first ingest, the head appearing
only from iteration 1.

What it does: load the source checkpoint through `build_net` +
`load_compat` (the same path the server and the drill scorer use), then
save the resulting state_dict. The payment params come out at their
design inits — `pay_bias[pay_class] = +2.0`, `pay_kind_emb` zero — so the
grafted checkpoint is behaviourally identical to the source everywhere
else, and identical to the state the day-zero drill baselines were banked
on (positive 2/64, auto-correct 196/214, deviation 8.6%).

Usage:
  uv run python scripts/graft_pay_init.py \
      --ckpt data/training/d6-run11/iter-019/train/last.pt \
      --out data/training/d4-init/last.pt
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ckpt", required=True, help="source checkpoint (no pay_ params)")
    ap.add_argument("--out", required=True, help="destination checkpoint path")
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()

    import torch

    from anvil.training.dataset import default_methods
    from anvil.training.train import build_net

    ckpt = torch.load(a.ckpt, map_location="cpu", weights_only=False)
    cfg = ckpt["config"]
    src_pay = sorted(k for k in ckpt["model"] if k.startswith("pay_"))
    if src_pay:
        raise SystemExit(f"source already carries pay_ params ({src_pay}) — nothing to graft")

    net = build_net(
        cfg["embed"], cfg["pool_manifest"], len(default_methods()), n_sa=cfg.get("sa_vocab_size", 0)
    ).to(a.device)
    net.load_compat(ckpt["model"])
    net.eval()

    state = {k: v.detach().cpu() for k, v in net.state_dict().items()}
    grafted = sorted(k for k in state if k.startswith("pay_"))
    if not grafted:
        raise SystemExit("build_net produced no pay_ params — wrong anvil revision?")

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({**ckpt, "model": state, "grafted_from": str(a.ckpt)}, out)

    print(f"[graft] source   {a.ckpt}")
    print(f"[graft] grafted  {', '.join(grafted)}")
    for k in grafted:
        v = state[k]
        print(
            f"[graft]   {k} shape={tuple(v.shape)} rms={float(v.float().pow(2).mean().sqrt()):.4f}"
        )
    print(f"[graft] wrote    {out}")


if __name__ == "__main__":
    main()
