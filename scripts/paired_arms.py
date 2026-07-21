"""Paired game-by-game comparison of two arms runs generated from the same
pairs file + seed base (the standing closeout comparison: matched seeds, so
per-game diffs cancel matchup/seed variance).

Each side is a comma-list of run dirs (the s0,s1 mirrored pair); runs are
matched positionally and games joined on index `i`. Model win = winner
string starts with "Anvil" (the bridged seat).

Usage:
  uv run python scripts/paired_arms.py \
      --a data/runs/run6-finalarm-s0-...,data/runs/run6-finalarm-s1-... \
      --b data/runs/run3-finalarm-s0-...,data/runs/run3-finalarm-s1-...
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _wins(run_dir: Path) -> dict[int, int]:
    out = {}
    for line in (run_dir / "games.jsonl").read_text().splitlines():
        g = json.loads(line)
        if g.get("status") != "won":
            continue
        out[g["i"]] = 1 if (g.get("winner") or "").startswith("Anvil") else 0
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="comma-list of run dirs (side A)")
    ap.add_argument("--b", required=True, help="comma-list of run dirs (side B)")
    args = ap.parse_args()

    a_dirs = [Path(p) for p in args.a.split(",")]
    b_dirs = [Path(p) for p in args.b.split(",")]
    if len(a_dirs) != len(b_dirs):
        raise SystemExit("side A and B need the same number of run dirs")

    diffs: list[int] = []
    for ad, bd in zip(a_dirs, b_dirs):
        aw, bw = _wins(ad), _wins(bd)
        # seed sanity: same index must mean the same seeded game
        sa = json.loads((ad / "run.json").read_text())
        sb = json.loads((bd / "run.json").read_text())
        for key in ("seed_base", "pairs_sha256", "n_pairs", "games_per_pair"):
            if sa.get(key) != sb.get(key):
                raise SystemExit(f"{ad.name} vs {bd.name}: {key} mismatch "
                                 f"({sa.get(key)} != {sb.get(key)}) — not paired")
        common = sorted(set(aw) & set(bw))
        diffs += [aw[i] - bw[i] for i in common]

    n = len(diffs)
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    se = math.sqrt(var / n)
    up = sum(1 for d in diffs if d > 0)
    down = sum(1 for d in diffs if d < 0)
    print(f"paired games: {n}")
    print(f"A - B: {mean * 100:+.2f}pp ± {se * 100:.2f} "
          f"(t={mean / se if se else float('inf'):.2f}, {up} up / {down} down)")


if __name__ == "__main__":
    main()
