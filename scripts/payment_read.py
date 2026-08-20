#!/usr/bin/env python3
"""M9 D3 rung 2: the payment-surface census read (m9-payment-surface-spec §8).

Reads census JSONL from a -paytelemetry (or payment-bridged) run and reports
the flag telemetry the spec owes BEFORE any model side trains:

- in-scope windows/game (the ~61/g budget line from the D3 scope pins)
- consequential-window rate + /game (the bridge-tax budget check)
- FORCED-window rate (the §4 amendment channel: one class, auto-unpayable —
  the purest veto-collapse channel, D5 reads it separately)
- class-count histogram; truncation rate vs the pinned 5% revisit gate
- bridged-window answer/exec distribution when the tag was actually bridged
  (pick auto vs class; directed_ok / directed_salvage / directed_fail;
  float_residue > 0 — all spec §7 reason codes, never vetoes)

Usage: payment_read.py <census.jsonl> [more.jsonl ...] [--json]

Telemetry fields are additive kv on the standing payManaCost census record —
files from runs without -paytelemetry parse fine and report zero coverage.
"""

import json
import sys
from collections import Counter


# The D3 scope-pin budget: in-scope (cast/activation, effect=false) traffic
# measured 2026-08-19 on run-20260704-dcpool. The consequential rate must
# land well under this for the 2.6% bridge tax to survive.
IN_SCOPE_BUDGET_PER_GAME = 61.0
# Pinned truncation revisit gate (spec §11).
TRUNCATION_GATE = 0.05


def read(paths: list[str]) -> dict:
    games: set = set()
    total = 0  # all payManaCost records
    effect_true = 0
    zero_skipped = 0  # in-scope-shape but no telemetry kv (mode off / zero-mana)
    scoped = 0  # records carrying telemetry (enumeration ran)
    conseq = 0
    forced = 0
    trunc = 0
    class_hist: Counter[int] = Counter()
    atoms_sum = 0
    picks: Counter[str] = Counter()  # bridged answers: "auto" or "class"
    execs: Counter[str] = Counter()  # directed_ok / directed_salvage / directed_fail
    residue_windows = 0

    for path in paths:
        with open(path) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("ev") == "start":
                    games.add((path, r.get("g")))
                    continue
                if r.get("m") != "payManaCost":
                    continue
                total += 1
                if r.get("effect"):
                    effect_true += 1
                    continue
                if "classes" not in r:
                    zero_skipped += 1
                    continue
                scoped += 1
                class_hist[int(r["classes"])] += 1
                atoms_sum += int(r.get("atoms", 0))
                if r.get("trunc"):
                    trunc += 1
                if r.get("conseq"):
                    conseq += 1
                    if r.get("forced"):
                        forced += 1
                pick = r.get("pick")
                if pick is not None:
                    picks["auto" if pick == "auto" else "class"] += 1
                if r.get("exec"):
                    execs[str(r["exec"])] += 1
                if int(r.get("float_residue", 0) or 0) > 0:
                    residue_windows += 1

    n_games = max(len(games), 1)
    return {
        "games": len(games),
        "pay_records": total,
        "effect_true": effect_true,
        "no_telemetry": zero_skipped,
        "scoped_windows": scoped,
        "scoped_per_game": scoped / n_games,
        "consequential": conseq,
        "consequential_rate": conseq / scoped if scoped else 0.0,
        "consequential_per_game": conseq / n_games,
        "forced": forced,
        "forced_rate": forced / scoped if scoped else 0.0,
        "truncated": trunc,
        "truncation_rate": trunc / conseq if conseq else 0.0,
        "class_hist": dict(sorted(class_hist.items())),
        "atoms_mean": atoms_sum / scoped if scoped else 0.0,
        "picks": dict(picks),
        "execs": dict(execs),
        "float_residue_windows": residue_windows,
    }


def report(stats: dict) -> str:
    lines = [
        "payment-surface census read (m9-payment-surface-spec §8)",
        f"  games                {stats['games']}",
        f"  payManaCost records  {stats['pay_records']} "
        f"(effect=true {stats['effect_true']}, no-telemetry {stats['no_telemetry']})",
        f"  scoped windows       {stats['scoped_windows']} "
        f"({stats['scoped_per_game']:.1f}/g; budget line {IN_SCOPE_BUDGET_PER_GAME:.0f}/g)",
        f"  consequential        {stats['consequential']} "
        f"(rate {stats['consequential_rate']:.4f}; {stats['consequential_per_game']:.2f}/g)",
        f"  forced windows       {stats['forced']} "
        f"(rate {stats['forced_rate']:.4f} of scoped)",
        f"  truncated            {stats['truncated']} "
        f"(rate {stats['truncation_rate']:.4f} of consequential; gate {TRUNCATION_GATE})",
        f"  class histogram      {stats['class_hist']}",
        f"  atoms mean           {stats['atoms_mean']:.1f}",
    ]
    if stats["picks"]:
        lines.append(f"  bridged picks        {stats['picks']}")
    if stats["execs"]:
        lines.append(f"  exec outcomes        {stats['execs']}")
    if stats["float_residue_windows"]:
        lines.append(f"  FLOAT RESIDUE        {stats['float_residue_windows']} windows (expected ~0)")
    if stats["truncation_rate"] > TRUNCATION_GATE:
        lines.append(
            f"  ** TRUNCATION GATE EXCEEDED ({stats['truncation_rate']:.4f} > "
            f"{TRUNCATION_GATE}) — the K_MAX cap design is revisited before D4 (spec §11) **"
        )
    return "\n".join(lines)


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    stats = read(args)
    print(json.dumps(stats, indent=2) if as_json else report(stats))


if __name__ == "__main__":
    main()
