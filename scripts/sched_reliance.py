#!/usr/bin/env python3
"""M10 v2: the schedule-reliance readout (m10-build-spec §5 family 1 — the
consumption instrument, run per accepted iteration on a FIXED population).

Measures, on a pinned sched-bearing store (fixed across iterations so the
series is comparable):
  reliance_l1     mean |Δ policy logits| (valid candidate slots) over
                  conditioned windows, slots FED vs mask-CLOSED
  argmax_flip     fraction of conditioned windows whose greedy action
                  changes when the slots close — the behavioral consumption
                  signal the kill/fund gates read
  aux_ce          decode CE on emission rows (holdout trend)
  aux_e_l1 / aux_r_l1   E/R smooth-L1 on their valid rows
  sched_rms       sched_proj weight rms (moved vs never moved)

Day-zero on the zero-init graft: argmax_flip is NOT structurally 0 — six
present-but-zero slot tokens perturb attention by PRESENCE (the v2 identity
contract, m10-build-spec §2). The day-zero run BANKS that number as the
reliance floor the KILL clause reads against; content-invariance (any two
schedules identical) is what zero-init guarantees, and the paired
`content_flip` readout asserts it (must be exactly 0 at day zero).
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
    from anvil.training.rl import RlTrajectories
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
        [args.store], [1.0], cfg["embed"], default_methods(), seg=128, sched=True
    )
    n_traj = 0
    l1_sum = l1_n = 0.0
    flips = content_flips = conditioned = 0
    ce_sum = ce_n = e_sum = e_n = r_sum = r_n = 0.0
    with torch.no_grad():
        for item in ds:
            if "skip" in item:
                continue
            segs = item["segs"]
            for s in segs:
                fed = {k: v.to(dev) for k, v in s.items() if torch.is_tensor(v)}
                has_cond = "sched_mask" in fed and bool(fed["sched_mask"].any())
                with torch.autocast(dev, dtype=torch.bfloat16):
                    out_f = net(fed)
                    if has_cond:
                        closed = dict(fed)
                        closed["sched_mask"] = torch.zeros_like(fed["sched_mask"])
                        out_c = net(closed)
                        # content probe: pos-rotated slots, same mask — must
                        # be bit-identical at zero init (content invariance)
                        perm = dict(fed)
                        perm["sched_rows"] = fed["sched_rows"].roll(1, dims=1)
                        perm["sched_sa"] = fed["sched_sa"].roll(1, dims=1)
                        out_p = net(perm)
                if has_cond:
                    rows = fed["sched_mask"].any(dim=1)
                    lf = out_f["policy_logits"].float()
                    lc = out_c["policy_logits"].float()
                    lp = out_p["policy_logits"].float()
                    valid = torch.cat(
                        [
                            torch.ones(lf.shape[0], 1, dtype=torch.bool, device=dev),
                            fed["cand_mask"][:, 1:],
                        ],
                        dim=1,
                    )
                    m = rows.unsqueeze(1) & valid
                    l1_sum += float((lf - lc).abs()[m].sum())
                    l1_n += float(m.sum())
                    am_f = lf.masked_fill(~valid, -1e9).argmax(1)
                    am_c = lc.masked_fill(~valid, -1e9).argmax(1)
                    am_p = lp.masked_fill(~valid, -1e9).argmax(1)
                    flips += int((am_f[rows] != am_c[rows]).sum())
                    content_flips += int((am_f[rows] != am_p[rows]).sum())
                    conditioned += int(rows.sum())
                fidx = fed["sched_emit"].nonzero(as_tuple=True)[0]
                if fidx.numel() and "sched_logits" in out_f:
                    lg = out_f["sched_logits"][fidx].float()
                    tgt = fed["sched_tgt_full"][fidx]
                    ce = F.cross_entropy(
                        lg.flatten(0, 1), tgt.flatten(0, 1),
                        ignore_index=-1, reduction="sum",
                    )
                    n_lab = int((tgt >= 0).sum())
                    if n_lab:
                        ce_sum += float(ce)
                        ce_n += n_lab
                    ev = fed["sched_e_valid"][fidx]
                    if ev.any():
                        e_sum += float(F.smooth_l1_loss(
                            out_f["sched_e"][fidx][ev].float(),
                            fed["sched_e_tgt"][fidx][ev], reduction="sum",
                        ))
                        e_n += int(ev.sum()) * 7
                    rv = fed["sched_r_valid"][fidx]
                    if rv.any():
                        r_sum += float(F.smooth_l1_loss(
                            out_f["sched_r"][fidx][rv].float(),
                            fed["sched_r_tgt"][fidx][rv], reduction="sum",
                        ))
                        r_n += int(rv.sum()) * 2
            n_traj += 1
            if n_traj >= args.max_traj:
                break

    report = {
        "ckpt": args.ckpt,
        "store": args.store,
        "n_traj": n_traj,
        "n_conditioned": conditioned,
        "reliance_l1": round(l1_sum / max(l1_n, 1), 6),
        "argmax_flip": round(flips / max(conditioned, 1), 6),
        "content_flip": round(content_flips / max(conditioned, 1), 6),
        "aux_ce": round(ce_sum / max(ce_n, 1), 6),
        "aux_e_l1": round(e_sum / max(e_n, 1), 6),
        "aux_r_l1": round(r_sum / max(r_n, 1), 6),
        "sched_rms": round(
            float(net.assemble.sched_proj.weight.square().mean().sqrt()), 8
        ),
    }
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
