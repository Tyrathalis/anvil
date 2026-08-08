"""Compare two card-neighbor recordings and report before/after drift.

Usage:
  uv run python scripts/compare_neighbors.py \
      data/neighbors/before.json data/neighbors/after.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("before", type=Path)
    ap.add_argument("after", type=Path)
    ap.add_argument("--top-movers", type=int, default=20)
    a = ap.parse_args()

    before: dict[str, Any] = json.loads(a.before.read_text())
    after: dict[str, Any] = json.loads(a.after.read_text())

    b_nei = before["neighbors"]
    a_nei = after["neighbors"]
    names = sorted(set(b_nei) & set(a_nei))

    jaccards = []
    unchanged = 0
    changes: list[tuple[str, float, int]] = []  # name, jaccard, changed_positions
    for name in names:
        b_set = {n["name"] for n in b_nei[name]}
        a_set = {n["name"] for n in a_nei[name]}
        jac = jaccard(b_set, a_set)
        jaccards.append(jac)
        if jac == 1.0:
            unchanged += 1
        # count positions where the ordered list changed
        changed_pos = sum(
            1 for i, (bn, an) in enumerate(zip(b_nei[name], a_nei[name]))
            if bn["name"] != an["name"]
        )
        changes.append((name, jac, changed_pos))

    mean_jac = sum(jaccards) / len(jaccards) if jaccards else 0.0
    median_jac = sorted(jaccards)[len(jaccards) // 2] if jaccards else 0.0

    print("=" * 60)
    print(f"Before: {a.before}")
    print(f"After:  {a.after}")
    print(f"Cards compared: {len(names)}")
    print(f"Mean neighbor-set Jaccard:   {mean_jac:.3f}")
    print(f"Median neighbor-set Jaccard: {median_jac:.3f}")
    print(f"Unchanged neighbor sets:     {unchanged}/{len(names)} ({100*unchanged/len(names):.1f}%)")
    print(f"Avg changed ordered positions: {sum(c[2] for c in changes)/len(changes):.2f} / {before['k']}")
    print("=" * 60)
    print("Top movers (lowest Jaccard):")
    for name, jac, changed_pos in sorted(changes, key=lambda x: (x[1], -x[2]))[:a.top_movers]:
        b_list = [n["name"] for n in b_nei[name]]
        a_list = [n["name"] for n in a_nei[name]]
        print(f"\n  {name:<40} Jaccard={jac:.2f} changed_pos={changed_pos}")
        print(f"    before: {b_list}")
        print(f"    after:  {a_list}")


if __name__ == "__main__":
    main()
