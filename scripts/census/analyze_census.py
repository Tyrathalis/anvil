#!/usr/bin/env python3
"""Analyze callback-census JSONL from `forge census`.

Outputs:
1. Per-method frequency table: total calls, calls/game (mean, p50, max), % of
   games in which the method fires at least once — ranks bridge serialization
   work by real traffic (override plan phase 2/3).
2. Cast-path sequences: for every playChosenSpellAbility entry, the nested
   callbacks (records with greater stack depth until depth returns to or below
   the entry's) — the empirical check on the one inferred claim in the
   override plan (mode/X/optional-cost callback order on the AI cast path).

Usage: analyze_census.py <census.jsonl> [more.jsonl ...]
"""

import json
import sys
from collections import Counter, defaultdict
from statistics import mean, median


def main(paths: list[str]) -> None:
    per_method_total = Counter()
    per_method_per_game = defaultdict(lambda: defaultdict(int))  # method -> game -> n
    games = set()
    game_events = defaultdict(list)  # game key -> [(seq, method, depth)]
    n_end = 0

    for path in paths:
        with open(path) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("ev") == "end":
                    n_end += 1
                    continue
                if r.get("ev") == "start" or "m" not in r:
                    continue
                key = (path, r["g"])
                games.add(key)
                per_method_total[r["m"]] += 1
                per_method_per_game[r["m"]][key] += 1
                game_events[key].append((r["s"], r["m"], r["d"]))

    n_games = len(games)
    print(f"# {n_games} games ({n_end} completed) across {len(paths)} file(s); "
          f"{sum(per_method_total.values())} callbacks, {len(per_method_total)} distinct methods\n")

    total_per_game = [sum(1 for _ in evs) for evs in game_events.values()]
    if total_per_game:
        print(f"callbacks/game: mean {mean(total_per_game):.0f}, "
              f"median {median(total_per_game):.0f}, max {max(total_per_game)}\n")

    print(f"{'method':44s} {'total':>8s} {'mean/g':>8s} {'p50/g':>6s} {'max/g':>6s} {'%games':>7s}")
    for m, tot in per_method_total.most_common():
        counts = per_method_per_game[m]
        vals = list(counts.values())
        pct = 100.0 * len(counts) / n_games if n_games else 0
        print(f"{m:44s} {tot:8d} {tot / n_games:8.1f} {median(vals):6.0f} "
              f"{max(vals):6d} {pct:6.1f}%")

    # Cast-path nesting: callbacks strictly inside each playChosenSpellAbility.
    seqs = Counter()
    for key, evs in game_events.items():
        evs.sort()
        i = 0
        while i < len(evs):
            seq, m, d = evs[i]
            if m == "playChosenSpellAbility":
                inner = []
                j = i + 1
                while j < len(evs) and evs[j][2] > d:
                    inner.append(evs[j][1])
                    j += 1
                seqs[tuple(inner)] += 1
                i = j
            else:
                i += 1

    print(f"\n# playChosenSpellAbility nested-callback sequences "
          f"({sum(seqs.values())} casts, {len(seqs)} distinct):")
    for s, n in seqs.most_common(25):
        print(f"{n:6d}  {' -> '.join(s) if s else '(none — fully pre-decided)'}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
