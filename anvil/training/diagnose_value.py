"""Value-head diagnostic (M1 D5): is the at-chance BCE an averaging artifact
or a representation gap?

pilot-run1 ended with val value BCE ~0.6913 vs ln2 0.6931 — almost exactly the
constant base-rate floor for p~0.53, i.e. the head may have learned only the
acting-player base rate. This script separates the hypotheses:

  - averaging artifact: late-game windows (turns_from_end small) show BCE well
    below the constant floor and AUC >> 0.5 — early ~50/50 windows just swamp
    the run-level average; the head is fine, report binned BCE going forward.
  - representation gap: late-game BCE sits at the constant floor and AUC ~0.5
    — outcome signal (life totals, board) is not reaching the value head in a
    usable form; that's a D4 architecture question and gates nothing on data.

Streams the split game-by-game (not via DataLoader) so each window gets
turns_from_end = last observed turn in its game minus its own turn.

  uv run python -m anvil.training.diagnose_value --ckpt data/training/pilot-run1/last.pt
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch

from anvil.encoder.transform import GLOBAL_FEATURES, GLOBAL_SCALE
from anvil.store.trajectories import TrajectoryStore
from anvil.training.dataset import (PriorityWindows, _split_of, collate,
                                    default_methods)
from anvil.training.train import build_net

TURN = GLOBAL_FEATURES.index("turn")
EPS = 1e-7

TURN_BINS = [(1, 4), (5, 8), (9, 12), (13, 16), (17, 20), (21, 10**9)]
FROM_END_BINS = [(0, 0), (1, 1), (2, 2), (3, 4), (5, 8), (9, 16), (17, 10**9)]


def bce(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, EPS, 1 - EPS)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def const_bce(rate: float, y: np.ndarray) -> float:
    return bce(np.full_like(y, rate, dtype=np.float64), y)


def auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Rank AUC (Mann-Whitney). Returns nan if one class is absent."""
    pos = labels == 1
    n1, n0 = int(pos.sum()), int((~pos).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    order = np.argsort(scores, kind="stable")
    ranks = np.empty(len(scores), dtype=np.float64)
    ranks[order] = np.arange(1, len(scores) + 1)
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


@torch.no_grad()
def collect(net, ds: PriorityWindows, store: TrajectoryStore, games: list[int],
            device: str, batch: int) -> dict[str, np.ndarray]:
    """Forward every window of every outcome-bearing game; keep per-window
    (prob, won, turn, turns_from_end)."""
    probs, wons, turns, from_end = [], [], [], []
    skipped = 0
    for g in games:
        try:
            wins = list(ds._examples(store, g))
        except Exception as e:
            if "did not decompress" in str(e):
                skipped += 1
                continue  # quarantined frame (store policy)
            raise
        if not wins or int(wins[0]["has_outcome"]) == 0:
            continue
        g_turns = np.array([float(w["globals"][TURN]) / GLOBAL_SCALE[TURN] for w in wins])
        last = g_turns.max()
        for i in range(0, len(wins), batch):
            chunk = collate(wins[i:i + batch])
            chunk = {k: v.to(device) for k, v in chunk.items()}
            with torch.autocast(device, dtype=torch.bfloat16):
                out = net(chunk)
            probs.append(torch.sigmoid(out["value_logit"].float()).cpu().numpy())
            wons.append(chunk["won"].cpu().numpy())
        turns.append(g_turns)
        from_end.append(last - g_turns)
    if skipped:
        print(f"[diag] skipped {skipped} quarantined game(s)")
    return {"prob": np.concatenate(probs), "won": np.concatenate(wons).astype(np.float64),
            "turn": np.concatenate(turns), "from_end": np.concatenate(from_end)}


def bin_table(d: dict[str, np.ndarray], key: str, bins: list[tuple[int, int]],
              base_rate: float) -> list[dict]:
    rows = []
    for lo, hi in bins:
        m = (d[key] >= lo) & (d[key] <= hi)
        if not m.any():
            continue
        y, p = d["won"][m], d["prob"][m]
        rate = float(y.mean())
        rows.append({
            "bin": f"{lo}-{'+' if hi > 10**8 else hi}",
            "n": int(m.sum()),
            "win_rate": round(rate, 4),
            "bce_model": round(bce(p, y), 4),
            "bce_const_global": round(const_bce(base_rate, y), 4),
            "bce_const_bin": round(const_bce(rate, y), 4),  # within-bin oracle floor
            "auc": round(auc(p, y), 4),
            "pred_std": round(float(p.std()), 4),
        })
    return rows


def calibration(d: dict[str, np.ndarray], n_bins: int = 10) -> list[dict]:
    edges = np.linspace(0, 1, n_bins + 1)
    rows = []
    for i in range(n_bins):
        m = (d["prob"] >= edges[i]) & (d["prob"] < edges[i + 1])
        if m.sum() < 20:
            continue
        rows.append({"pred_bin": f"[{edges[i]:.1f},{edges[i+1]:.1f})",
                     "n": int(m.sum()),
                     "mean_pred": round(float(d["prob"][m].mean()), 4),
                     "empirical": round(float(d["won"][m].mean()), 4)})
    return rows


def fmt(rows: list[dict]) -> str:
    if not rows:
        return "  (no rows)"
    cols = list(rows[0])
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
    lines = ["  " + "  ".join(c.rjust(widths[c]) for c in cols)]
    for r in rows:
        lines.append("  " + "  ".join(str(r[c]).rjust(widths[c]) for c in cols))
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="data/training/pilot-run1/last.pt")
    ap.add_argument("--split", default="val", choices=["val", "valpair", "train"])
    ap.add_argument("--max-games", type=int, default=None)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--out", default=None, help="JSON report path (default: beside ckpt)")
    a = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    ckpt = torch.load(a.ckpt, map_location=device, weights_only=False)
    cfg = ckpt["config"]
    methods = default_methods()
    net = build_net(cfg["embed"], cfg["pool_manifest"], len(methods)).to(device)
    net.load_state_dict(ckpt["model"])
    net.eval()

    ds = PriorityWindows(cfg["store"], cfg["embed"], methods,
                         split=a.split, shuffle_games=False)
    store = TrajectoryStore(cfg["store"])
    games = [g for g in store.game_indices() if _split_of(g) == a.split]
    if a.max_games:
        games = games[:a.max_games]
    print(f"[diag] ckpt step {ckpt['step']}, split={a.split}, {len(games)} games")

    d = collect(net, ds, store, games, device, a.batch)
    y, p = d["won"], d["prob"]
    base = float(y.mean())
    report = {
        "ckpt": a.ckpt, "step": ckpt["step"], "split": a.split,
        "windows": int(len(y)), "games": len(games),
        "base_rate_acting_player": round(base, 4),
        "bce_model": round(bce(p, y), 4),
        "bce_const_half": round(math.log(2), 4),
        "bce_const_base_rate": round(const_bce(base, y), 4),
        "auc": round(auc(p, y), 4),
        "pred_mean": round(float(p.mean()), 4),
        "pred_std": round(float(p.std()), 4),
        "pred_p05": round(float(np.quantile(p, 0.05)), 4),
        "pred_p95": round(float(np.quantile(p, 0.95)), 4),
        "by_turn": bin_table(d, "turn", TURN_BINS, base),
        "by_turns_from_end": bin_table(d, "from_end", FROM_END_BINS, base),
        "calibration": calibration(d),
    }

    print(f"\n[diag] {report['windows']} windows | acting-player base rate {base:.4f}")
    print(f"[diag] BCE model {report['bce_model']} | const 0.5 {report['bce_const_half']} "
          f"| const base-rate {report['bce_const_base_rate']} | AUC {report['auc']}")
    print(f"[diag] pred spread: mean {report['pred_mean']} std {report['pred_std']} "
          f"p05 {report['pred_p05']} p95 {report['pred_p95']}")
    print("\n[diag] by turn:")
    print(fmt(report["by_turn"]))
    print("\n[diag] by turns-from-end:")
    print(fmt(report["by_turns_from_end"]))
    print("\n[diag] calibration:")
    print(fmt(report["calibration"]))

    out = Path(a.out or Path(a.ckpt).parent / f"value_diag_{a.split}.json")
    out.write_text(json.dumps(report, indent=1) + "\n")
    print(f"\n[diag] report -> {out}")


if __name__ == "__main__":
    main()
