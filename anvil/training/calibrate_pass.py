"""PASS-logit calibration (M1 D8). uv run python -m anvil.training.calibrate_pass ...

pw=0.1 trains an action-rich prior (D5 sweep: +11pp nonpass for ~-1.7pp honest);
the honest cost is the pass boundary, and the D5 premise is that it's
recoverable post-hoc. This fits the recovery: a scalar offset added to the PASS
logit at play time, chosen so the model's pass rate matches the expert's on
held-out multi-candidate priority windows. Logits are cached once, so the
offset search and the before/after metrics are exact on the same windows.

Writes pass_calibration.json next to the checkpoint; the D8 executor reads it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from anvil.training.dataset import PriorityWindows, collate, default_methods
from anvil.training.train import build_net


@torch.no_grad()
def collect(net, loader, device: str, max_batches: int) -> dict[str, torch.Tensor]:
    """One forward pass over val; keep per-window scalars sufficient to score
    any PASS offset offline: the PASS logit, the best non-PASS logit, whether
    the non-PASS argmax is the expert's pick, and the expert's pass/multi flags."""
    cols = {k: [] for k in ("pass_logit", "best_np", "np_correct", "label_pass", "multi")}
    for i, batch in enumerate(loader):
        if i >= max_batches:
            break
        batch = {k: v.to(device) for k, v in batch.items()}
        with torch.autocast(device, dtype=torch.bfloat16):
            out = net(batch)
        logits = out["policy_logits"].float()
        np_logits = logits.clone()
        np_logits[:, 0] = -1e9  # padding already masked to -1e9 in forward
        best_np, arg_np = np_logits.max(1)
        cols["pass_logit"].append(logits[:, 0].cpu())
        cols["best_np"].append(best_np.cpu())
        cols["np_correct"].append((arg_np == batch["label"]).cpu())
        cols["label_pass"].append((batch["label"] == 0).cpu())
        cols["multi"].append((batch["cand_mask"].sum(1) > 1).cpu())
    return {k: torch.cat(v) for k, v in cols.items()}


def metrics_at(c: dict[str, torch.Tensor], delta: float) -> dict:
    pred_pass = c["pass_logit"] + delta > c["best_np"]
    agree = torch.where(pred_pass, c["label_pass"], ~c["label_pass"] & c["np_correct"])
    m, np_ = c["multi"], ~c["label_pass"]
    return {
        "delta": delta,
        "pass_rate": pred_pass[m].float().mean().item(),
        "agree_honest": agree[m].float().mean().item(),
        "agree_raw": agree.float().mean().item(),
        "agree_nonpass": agree[np_].float().mean().item(),
    }


def fit_delta(c: dict[str, torch.Tensor]) -> float:
    """Pass rate is monotone in delta; bisect to the expert's rate."""
    target = c["label_pass"][c["multi"]].float().mean().item()
    lo, hi = -30.0, 30.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if metrics_at(c, mid)["pass_rate"] < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--batches", type=int, default=600)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    ckpt = torch.load(a.ckpt, map_location=device, weights_only=False)
    cfg = ckpt["config"]
    net = build_net(cfg["embed"], cfg["pool_manifest"], len(default_methods()),
                    n_sa=cfg.get("sa_vocab_size", 0)).to(device)
    net.load_compat(ckpt["model"])
    net.eval()

    ds = PriorityWindows(cfg["store"], cfg["embed"], default_methods(), split="val",
                         shuffle_games=False, tasks={"priority"})
    loader = DataLoader(ds, batch_size=a.batch, collate_fn=collate, num_workers=a.workers)
    c = collect(net, loader, device, a.batches)

    expert_rate = c["label_pass"][c["multi"]].float().mean().item()
    delta = fit_delta(c)
    before, after = metrics_at(c, 0.0), metrics_at(c, delta)
    n = int(c["multi"].sum())
    report = {"ckpt": a.ckpt, "delta": delta, "expert_pass_rate": expert_rate,
              "n_multi": n, "n_windows": int(c["multi"].numel()),
              "before": before, "after": after,
              "pass_weight": cfg.get("pass_weight")}
    out = Path(a.ckpt).parent / "pass_calibration.json"
    out.write_text(json.dumps(report, indent=1) + "\n")
    print(f"[calibrate] expert pass rate {expert_rate:.4f} on {n} multi windows")
    for tag, r in (("delta=0", before), (f"delta={delta:.3f}", after)):
        print(f"[calibrate] {tag}: pass {r['pass_rate']:.4f} honest {r['agree_honest']:.4f} "
              f"nonpass {r['agree_nonpass']:.4f} raw {r['agree_raw']:.4f}")
    print(f"[calibrate] wrote {out}")


if __name__ == "__main__":
    main()
