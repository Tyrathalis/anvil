"""The 10-01 baseline reads: the test seat's win rate and its compute cost per arm.

Each --arm is name=s0_run_dir,s1_run_dir (final_read's two seat runs; the run
dir's -s0- / -s1- names the test seat). The test seat is the bridged or random
or searched or simulating seat; a game counts as a test-seat win when its
winner string carries "(seat+1)" (AnvilRun names seats "Anvil(n)" / "Heur(n)"
/ "Rand(n)", 1-based), so it holds whatever the seat prefixes are. Draws,
caps and crashes count as non-wins (arms_report's convention).

Cost: game wall ms per priority window (games.jsonl "ms" / "windows"), mean and
median, beside games per hour per worker. Every arm of one chain runs on one
quiet box at one worker count, against the same heuristic, so the ratio to the
heuristic mirror's ms per window is the test seat's added compute.

Usage:
  uv run python scripts/baseline_reads.py --arm heur=d0,d1 --arm randheur=d0,d1 \
      --ref heur --out data/runs/baseline-reads/reads.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path


def seat_of(run_dir: Path) -> int:
    name = run_dir.name
    if "-s0-" in name:
        return 0
    if "-s1-" in name:
        return 1
    raise ValueError(f"no -s0- / -s1- in {name}")


def _games_lines(rd: Path) -> list[str]:
    """The merged games.jsonl, or — for a probe the harness never completed
    (a timeout, or its zero-game abort: the 10-03 simfull probe) — the
    workers' own files, which hold every game already written."""
    merged = rd / "games.jsonl"
    if merged.exists():
        return merged.read_text().splitlines()
    lines: list[str] = []
    for f in sorted(rd.glob("workers/inv-*/games.jsonl")):
        lines += f.read_text().splitlines()
    return lines


def read_arm(dirs: list[Path]) -> dict:
    games = wins = crashes = capped = 0
    per_window: list[float] = []
    ms: list[float] = []
    turns: list[int] = []
    for rd in dirs:
        seat = seat_of(rd)
        tag = f"({seat + 1})"
        for line in _games_lines(rd):
            g = json.loads(line)
            games += 1
            status = g.get("status", "")
            if status.startswith("crash"):
                crashes += 1
            if status != "won":
                capped += 1  # draws, caps and crashes
            if tag in (g.get("winner") or ""):
                wins += 1
            if g.get("ms") and g.get("windows"):
                ms.append(g["ms"])
                per_window.append(g["ms"] / g["windows"])
            turns.append(g.get("turns", 0))
    wr = wins / games if games else float("nan")
    return {
        "runs": [str(d) for d in dirs],
        "games": games,
        "wins": wins,
        "crashes": crashes,
        "not_won": capped,
        "winrate": wr,
        "se": math.sqrt(wr * (1 - wr) / games) if games else float("nan"),
        "ms_per_window_mean": statistics.fmean(per_window) if per_window else None,
        "ms_per_window_median": statistics.median(per_window) if per_window else None,
        "game_s_median": statistics.median(ms) / 1000 if ms else None,
        "turns_mean": statistics.fmean(turns) if turns else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", action="append", required=True, help="name=s0_dir,s1_dir")
    ap.add_argument("--ref", default=None, help="the arm whose ms per window is the cost unit")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    arms = {}
    for spec in a.arm:
        name, dirs = spec.split("=", 1)
        arms[name] = read_arm([Path(d) for d in dirs.split(",") if d])
    ref = arms.get(a.ref) if a.ref else None
    for r in arms.values():
        unit = ref and ref["ms_per_window_mean"]
        r["cost_x_ref"] = r["ms_per_window_mean"] / unit if unit and r["ms_per_window_mean"] else None
    a.out.write_text(json.dumps(arms, indent=2) + "\n")
    print("| arm | games | test-seat winrate | crashes | ms / window (mean) | × ref | median game (s) |")
    print("|---|---|---|---|---|---|---|")
    for name, r in arms.items():
        x = f"{r['cost_x_ref']:.2f}" if r["cost_x_ref"] else "—"
        mpw = f"{r['ms_per_window_mean']:.1f}" if r["ms_per_window_mean"] else "—"
        gs = f"{r['game_s_median']:.1f}" if r["game_s_median"] else "—"
        if not r["games"]:
            print(f"| {name} | 0 | — (no games: the arm failed) | — | — | — | — |")
            continue
        print(f"| {name} | {r['games']} | {r['winrate']:.4f} ± {r['se']:.4f} | {r['crashes']} | {mpw} | {x} | {gs} |")


if __name__ == "__main__":
    main()
