"""D5: integration cross-check — the loader's combat examples vs the
measure-script record, on the same games. Runs the REAL dataset path
(PriorityWindows with tasks={attack, block}, full assemble + embedding
rows + collate-ready fields), so what it counts is exactly what trains.

Beyond reproducing the measure counts, it prices the label classes only
the loader defines: mixed-target groups (attack target masked), split /
multi-block groups (block pointer masked), count-label coverage.

  uv run python scripts/d5/loader_combat_check.py --max-games 2000
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from anvil.training.dataset import PriorityWindows, default_methods


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="data/trajectories/d3pilot-20260704-175219")
    ap.add_argument("--embed", default="data/embeddings/cf2ca6ba-qwen3")
    ap.add_argument("--max-games", type=int, default=2000)
    ap.add_argument("--out", default="data/training/d5-loader-combat-check.json")
    a = ap.parse_args()

    ds = PriorityWindows(a.store, a.embed, default_methods(), shuffle_games=False,
                         max_games=a.max_games, tasks={"attack", "block"})
    st = Counter()
    for ex in ds:
        t = int(ex["task"])
        if t == 6:  # attack
            st["atk_windows"] += 1
            lab = ex["atk_label"].tolist()
            st["atk_rows"] += len(lab)
            st["atk_rows_attacking"] += sum(lab)
            if any(lab):
                st["atk_nonempty"] += 1
            for k, tk in zip(ex["cmb_count_label"].tolist(),
                             ex["atk_tgt_kind"].tolist()):
                if k >= 0:
                    st["atk_count_labels"] += 1
                if tk == 1:
                    st["atk_tgt_player"] += 1
                elif tk == 0:
                    st["atk_tgt_permanent"] += 1
            st["atk_tgt_masked"] += sum(
                1 for l, tk in zip(lab, ex["atk_tgt_kind"].tolist())
                if l == 1 and tk == -1)
        else:       # block
            st["blk_windows"] += 1
            none = ex["blk_atk_rows"].shape[0]
            lab = ex["blk_label"].tolist()
            st["blk_rows"] += len(lab)
            st["blk_rows_blocking"] += sum(1 for x in lab if 0 <= x < none)
            st["blk_rows_masked"] += sum(1 for x in lab if x == -1)
            if any(0 <= x < none for x in lab) or -1 in lab:
                st["blk_nonempty"] += 1
            st["blk_count_labels"] += sum(
                1 for k in ex["cmb_count_label"].tolist() if k >= 0)

    report = {"store": a.store, "max_games": a.max_games, "stats": dict(st)}
    with open(a.out, "w") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report["stats"], indent=1, sort_keys=True))
    print(f"report -> {a.out}")


if __name__ == "__main__":
    main()
