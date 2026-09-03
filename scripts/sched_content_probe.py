#!/usr/bin/env python3
"""Label-shaped content probe (ADR-0093 adjudication, 2026-09-02).

The pinned reliance population (`sched_reliance.py`) feeds day-zero
six-slot emissions (36% one card repeated six times). This probe feeds
LABEL-shaped schedules through the ADR-0092 follow-batch builder — the
certified arm at the windows the follow term trains on (`--src certified`,
in-sample), or the natural line at windows it never trains on
(`--src natural`, held-out for the pointer) — and reads, per ckpt:

  follow_acc_fed / follow_acc_closed   argmax == the arm's first cast with
                                       the schedule fed vs mask-closed
                                       (fed − closed = schedule-conditioned
                                       following; closed alone = BC)
  swap_flip (2-slot rows)              argmax changes when slots 0 and 1
                                       are swapped — a legal-candidate
                                       content change
  roll_flip_2slot                      the sched_reliance.py roll, for
                                       comparability

Standing rule: serve-side follow/utilization counters inflate on
natural-line plans; consumption must be read fed-vs-closed on label-
shaped inputs. Telemetry only under the M10 reset (m10-reset-draft §F.3).
"""

import argparse
import json

import torch

MINT = "data/runs/sched-mint-20260830"
DEFAULT_LABELS = ",".join([
    f"{MINT}/store-m10-probe1-i000-20260828-191848/labels-full.jsonl",
    f"{MINT}/store-m10-probe2-i000-20260829-123734/labels-full.jsonl",
])
DEFAULT_STORES = ",".join([
    "data/trajectories/m10-probe1-i000-20260828-191848",
    "data/trajectories/m10-probe2-i000-20260829-123734",
])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpts", nargs="+")
    ap.add_argument("--labels", default=DEFAULT_LABELS, help="comma-list, parallel to --stores")
    ap.add_argument("--stores", default=DEFAULT_STORES)
    ap.add_argument("--src", default="certified", choices=["certified", "natural"])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out", default=None, help="jsonl of per-ckpt rows")
    args = ap.parse_args()

    from anvil.bridge.featurize import Featurizer
    from anvil.training.dataset import SCHED_CAP, default_methods
    from anvil.training.seedlabels import build_follow_batch
    from anvil.training.train import build_net

    dev = args.device
    cfg = torch.load(args.ckpts[0], map_location="cpu", weights_only=False)["config"]
    methods = default_methods()
    feat = Featurizer(cfg["embed"], methods)
    segs = []
    for lp, sp in zip(args.labels.split(","), args.stores.split(",")):
        b = build_follow_batch(lp, sp, feat, seg=64, src=args.src)
        if b is None:
            print(f"[probe] {lp}: joined ZERO windows")
            continue
        print(f"[probe] {lp.split('/')[-2]}: {b['n']} windows (miss {b['miss']}, "
              f"unmatched {b['unmatched']}, retimed {b['retimed']})", flush=True)
        segs += b["segs"]
    if not segs:
        raise SystemExit("nothing joined")
    slot_keys = [k for k in segs[0] if k.startswith("sched_") and segs[0][k].dim() >= 2
                 and segs[0][k].shape[1] == SCHED_CAP and k != "sched_mask"]

    out = open(args.out, "a") if args.out else None
    for ckpt_path in args.ckpts:
        ck = torch.load(ckpt_path, map_location=dev, weights_only=False)
        net = build_net(cfg["embed"], cfg["pool_manifest"], len(methods),
                        n_sa=cfg.get("sa_vocab_size", 0)).to(dev)
        net.load_compat(ck["model"])
        net.eval()
        n = acc_f = acc_c = n2 = swap_flip = swap_leave = roll_flip = 0
        with torch.no_grad():
            for s in segs:
                fed = {k: v.to(dev) for k, v in s.items() if torch.is_tensor(v)}
                tgt = fed["follow_tgt"]
                valid = torch.cat(
                    [torch.ones(tgt.shape[0], 1, dtype=torch.bool, device=dev), fed["cand_mask"][:, 1:]], 1
                )

                def am(inp):
                    with torch.autocast(dev, dtype=torch.bfloat16):
                        o = net(inp)
                    return o["policy_logits"].float().masked_fill(~valid, -1e9).argmax(1)

                a_f = am(fed)
                closed = dict(fed)
                closed["sched_mask"] = torch.zeros_like(fed["sched_mask"])
                a_c = am(closed)
                swap = dict(fed)
                for k in slot_keys:
                    t = fed[k].clone()
                    t[:, [0, 1]] = fed[k][:, [1, 0]]
                    swap[k] = t
                a_s = am(swap)
                roll = dict(fed)
                for k in slot_keys:
                    roll[k] = fed[k].roll(1, dims=1)
                a_r = am(roll)
                two = fed["sched_mask"][:, 1]
                n += int(tgt.numel())
                acc_f += int((a_f == tgt).sum())
                acc_c += int((a_c == tgt).sum())
                n2 += int(two.sum())
                swap_flip += int(((a_s != a_f) & two).sum())
                swap_leave += int(((a_f == tgt) & (a_s != tgt) & two).sum())
                roll_flip += int(((a_r != a_f) & two).sum())
        row = {
            "ckpt": ckpt_path, "src": args.src, "n": n,
            "follow_acc_fed": round(acc_f / n, 4), "follow_acc_closed": round(acc_c / n, 4),
            "n_2slot": n2, "swap_flip": round(swap_flip / max(n2, 1), 4),
            "swap_leaves_tgt_given_followed": round(swap_leave / max(acc_f, 1), 4),
            "roll_flip_2slot": round(roll_flip / max(n2, 1), 4),
        }
        print(json.dumps(row), flush=True)
        if out:
            out.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    main()
