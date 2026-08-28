"""Graft the M10 v2 schedule-surface params onto the ckpt of record
(m10-build-spec §2/§6 R4 — the graft_plan_init pattern).

The serve path gates the schedule CARRY on the checkpoint carrying sched
params (`server.carry_sched`), so the graft materializes them:
assemble.sched_proj at ZERO init (the v2 identity contract — slot tokens
are content-invariant zeros until trained), decode/E/R heads + slot
embeddings at fresh init (supervised-only surfaces).

Two deliberate differences from the D6 graft, both design pins:
- pay_* params are KEPT (fresh at the rung-3 design inits: pay_bias +2.0,
  pay_kind_emb zero) — ADR-0073's attribution stripping is deliberately
  ENDED (m10-plan actuation pin 4); the M10 ckpt carries both surfaces
  entangled BY CHARTER, and serve re-advertises the pay tag.
- v1 plan params (plan_* heads + assemble.plan_proj) are STRIPPED: the v1
  float-vec carry is frozen legacy — carry_plan stays OFF and the discrete
  schedule carry is the only conditioning channel. (assemble.plan_tok is a
  base param since M1 and stays — it IS the [PLAN] readout slot.)

Usage:
  uv run python scripts/graft_sched_init.py \
      --ckpt data/training/d6-run11/iter-019/train/last.pt \
      --out data/training/m10-sched-init/last.pt
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
    if any(k.startswith(("sched_", "assemble.sched_")) for k in ckpt["model"]):
        raise SystemExit("source already carries sched params — nothing to graft")

    net = build_net(
        cfg["embed"], cfg["pool_manifest"], len(default_methods()),
        n_sa=cfg.get("sa_vocab_size", 0),
    )
    net.load_compat(ckpt["model"])
    state = net.state_dict()
    dropped = sorted(
        k for k in state if k.startswith(("plan_", "assemble.plan_proj."))
    )
    for k in dropped:
        del state[k]
    new_sched = sorted(
        k for k in state
        if k.startswith(("sched_", "assemble.sched_")) and k not in ckpt["model"]
    )
    new_pay = sorted(k for k in state if k.startswith("pay_") and k not in ckpt["model"])
    proj_rms = float(net.assemble.sched_proj.weight.square().mean().sqrt())
    if proj_rms != 0.0:
        raise SystemExit(f"sched_proj not zero-init (rms {proj_rms}) — identity contract broken")

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({**ckpt, "model": state}, out)
    print(f"grafted {a.ckpt} -> {out}")
    print(f"  new sched params ({len(new_sched)}): {new_sched}")
    print(f"  KEPT pay params at design init ({len(new_pay)}): {new_pay}")
    print(f"  stripped v1 plan params ({len(dropped)}): {dropped}")
    print(f"  sched_proj rms {proj_rms} (zero => content-invariant day zero)")


if __name__ == "__main__":
    main()
