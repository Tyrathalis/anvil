#!/usr/bin/env python3
"""M9 D6: the plan-reliance readout (m9-d6-plan-latent-spec §6/§7 — the
kill-signal instrument, run per accepted iteration on a FIXED population).

Measures, on a pinned store (fixed across iterations so the series is
comparable):
  reliance_l1      mean |Δ policy logits| (valid candidate slots), carried
                   windows, plan fed vs zeroed — the raw consumption signal
  argmax_flip      fraction of carried windows whose greedy action changes
                   when the plan is zeroed — the behavioral consumption
                   signal the kill/fund gates read
  aux_act_bce      emission-head action BCE on the fixed population
  aux_delta_l1     emission-head delta SmoothL1 (valid rows)
  vec_std          across-turn std of emitted vectors (informativeness)
  plan_rms         plan_proj weight rms (moved vs never moved)

Day-zero on the zero-init graft reads exactly 0 / 0 by construction — the
banked baseline is the aux pair + the assertion of those zeros.
"""

import argparse
import json
from pathlib import Path

import torch
import torch.nn.functional as F


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--store", required=True, help="the PINNED fixed population")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-traj", type=int, default=40)
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    from anvil.training.dataset import default_methods
    from anvil.training.rl import RlTrajectories, plan_pass0
    from anvil.training.train import build_net

    dev = args.device
    ckpt = torch.load(args.ckpt, map_location=dev, weights_only=False)
    cfg = ckpt["config"]
    net = build_net(
        cfg["embed"], cfg["pool_manifest"], len(default_methods()),
        n_sa=cfg.get("sa_vocab_size", 0),
    ).to(dev)
    net.load_compat(ckpt["model"])
    net.eval()

    ds = RlTrajectories(
        [args.store], [1.0], cfg["embed"], default_methods(), seg=128, plan=True
    )
    n_traj = 0
    l1_sum = l1_n = 0.0
    flips = carried = 0
    bce_sum = bce_n = dl_sum = dl_n = 0.0
    vecs = []
    with torch.no_grad():
        for item in ds:
            if "skip" in item:
                continue
            segs = item["segs"]
            plan_pass0(net, segs, dev)
            for s in segs:
                fed = {k: v.to(dev) for k, v in s.items() if torch.is_tensor(v)}
                zero = dict(fed)
                zero["has_plan"] = torch.zeros_like(fed["has_plan"])
                with torch.autocast(dev, dtype=torch.bfloat16):
                    out_f = net(fed)
                    out_z = net(zero)
                rows = fed["has_plan"].bool()
                if rows.any():
                    lf = out_f["policy_logits"].float()
                    lz = out_z["policy_logits"].float()
                    valid = fed["cand_mask"]
                    pad = torch.zeros(lf.shape[0], 1, dtype=torch.bool, device=dev)
                    valid = torch.cat([~pad, valid], dim=1)[:, : lf.shape[1]]
                    m = rows.unsqueeze(1) & valid
                    l1_sum += float((lf - lz).abs()[m].sum())
                    l1_n += float(m.sum())
                    am_f = lf.masked_fill(~valid, -1e9).argmax(1)
                    am_z = lz.masked_fill(~valid, -1e9).argmax(1)
                    flips += int((am_f[rows] != am_z[rows]).sum())
                    carried += int(rows.sum())
                fidx = fed["plan_first"].nonzero(as_tuple=True)[0]
                if fidx.numel():
                    pv = out_f["plan"][fidx].float()
                    vecs.append(pv.cpu())
                    bce = F.binary_cross_entropy_with_logits(
                        net.plan_act_head(pv).float(),
                        fed["plan_act_tgt"][fidx], reduction="sum",
                    )
                    bce_sum += float(bce)
                    bce_n += fidx.numel() * fed["plan_act_tgt"].shape[1]
                    dv = fed["plan_delta_valid"][fidx].bool()
                    if dv.any():
                        dl = F.smooth_l1_loss(
                            net.plan_delta_head(pv[dv]).float(),
                            fed["plan_delta_tgt"][fidx][dv], reduction="sum",
                        )
                        dl_sum += float(dl)
                        dl_n += int(dv.sum()) * fed["plan_delta_tgt"].shape[1]
            n_traj += 1
            if n_traj >= args.max_traj:
                break

    allv = torch.cat(vecs) if vecs else torch.zeros(1, 1)
    report = {
        "ckpt": args.ckpt,
        "store": args.store,
        "n_traj": n_traj,
        "n_carried": carried,
        "reliance_l1": round(l1_sum / max(l1_n, 1), 6),
        "argmax_flip": round(flips / max(carried, 1), 6),
        "aux_act_bce": round(bce_sum / max(bce_n, 1), 6),
        "aux_delta_l1": round(dl_sum / max(dl_n, 1), 6),
        "vec_std": round(float(allv.std(0).mean()), 6),
        "plan_rms": round(
            float(net.assemble.plan_proj.weight.square().mean().sqrt()), 8
        ),
    }
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
