"""Graft the M9 D6 plan-latent params onto the ckpt of record (build/graft
rung, m9-d6-plan-latent-spec §8 step 2 — the d4-init pattern).

The serve path gates the plan CARRY on the checkpoint carrying plan params
(`server.carry_plan`, the has_pay convention), and the loop serves --ckpt
directly at iteration 0 — an ungrafted launch would run the whole probe
with the carry off. The graft loads the source through build_net +
load_compat (the server's own path) and saves the state_dict: plan_proj at
ZERO init (day-zero bit-identity), aux heads at fresh init (only ever
touched by the aux loss).

pay_* params are deliberately STRIPPED from the output: ADR-0073 routed
the payment surface to infrastructure, so the D6 runs must not advertise
the pay tag — payment windows stay on engine auto-payment and the D6
attribution stays pure-latent.

Usage:
  uv run python scripts/graft_plan_init.py \
      --ckpt data/training/d6-run11/iter-019/train/last.pt \
      --out data/training/d6-plan-init/last.pt
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ckpt", required=True, help="source checkpoint")
    ap.add_argument("--out", required=True, help="destination checkpoint path")
    a = ap.parse_args()

    import torch

    from anvil.training.dataset import default_methods
    from anvil.training.train import build_net

    ckpt = torch.load(a.ckpt, map_location="cpu", weights_only=False)
    cfg = ckpt["config"]
    if any(k.startswith(("plan_", "assemble.plan_proj")) for k in ckpt["model"]):
        raise SystemExit("source already carries plan params — nothing to graft")

    net = build_net(
        cfg["embed"], cfg["pool_manifest"], len(default_methods()),
        n_sa=cfg.get("sa_vocab_size", 0),
    )
    net.load_compat(ckpt["model"])
    state = net.state_dict()
    dropped = sorted(k for k in state if k.startswith("pay_"))
    for k in dropped:
        del state[k]
    new = sorted(
        k for k in state
        if k.startswith(("plan_", "assemble.plan_proj")) and k not in ckpt["model"]
    )
    proj_rms = float(net.assemble.plan_proj.weight.square().mean().sqrt())
    if proj_rms != 0.0:
        raise SystemExit(f"plan_proj not zero-init (rms {proj_rms}) — day-zero identity broken")

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({**ckpt, "model": state}, out)
    print(f"grafted {a.ckpt} -> {out}")
    print(f"  new plan params: {new}")
    print(f"  stripped pay params ({len(dropped)}): {dropped}")
    print(f"  plan_proj rms {proj_rms} (zero => day-zero bit-identical)")


if __name__ == "__main__":
    main()
