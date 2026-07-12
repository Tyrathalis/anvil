"""Aggregate winrate-arm harness runs into an arms report (formalized from
the D8 scratchpad step per the reuse rule; produces the d8-arms-report.json
shape).

Each --arm is name=run_dir[,run_dir...]; model wins are games whose winner
string starts with "Anvil" (the bridged seat), so mirrored s0/s1 runs
aggregate naturally. Census tallies (priority pass/cast, rung, veto reasons,
mulligan) come from workers/inv-*/census.jsonl; heuristic arms have no
bridge records and report seat0_winrate instead.

Usage:
  uv run python scripts/arms_report.py \
      --arm heuristic=data/runs/d8arm-heur-20260710-102911 \
      --arm d0=data/runs/d3arm-d0-s0-...,data/runs/d3arm-d0-s1-... \
      --out data/runs/d3-arms-report.json
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

PRIORITY = "chooseSpellAbilityToPlay"


def aggregate(run_dirs: list[Path]) -> dict:
    games = decisive = draw_clock = crashes = 0
    model_wins = 0
    bridged_games = 0  # games from runs with a bridged seat (run.json)
    seat0_wins = 0
    turns = []
    prio = Counter()
    rungs = Counter()
    vetoes = Counter()
    mull = Counter()

    for rd in run_dirs:
        # NB: in pure-heuristic runs every seat is named "Anvil(n)-deck";
        # only bridged runs name the non-bridged seat "Heur(n)". The bridged
        # seat must come from run.json, never from winner-string sniffing.
        bridged = json.loads((rd / "run.json").read_text()).get("bridge_seats") is not None
        for line in (rd / "games.jsonl").read_text().splitlines():
            g = json.loads(line)
            games += 1
            turns.append(g.get("turns", 0))
            status = g.get("status", "")
            if status == "won":
                decisive += 1
            if status.startswith("crash"):
                crashes += 1
            if g.get("draw_clock"):
                draw_clock += 1
            winner = g.get("winner") or ""
            if bridged:
                bridged_games += 1  # crashes/draws count against the model
                if winner.startswith("Anvil"):
                    model_wins += 1
            elif "(1)" in winner:
                seat0_wins += 1
        for cf in sorted(rd.glob("workers/inv-*/census.jsonl")):
            for line in cf.read_text().splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                m = r.get("m")
                if m == PRIORITY and r.get("by") == "bridge":
                    if r.get("veto"):
                        vetoes[r.get("veto") if isinstance(r["veto"], str)
                               else r.get("reason", "veto")] += 1
                    elif r.get("pick") == "pass":
                        prio["pass"] += 1
                    else:
                        prio["cast"] += 1
                        if r.get("rung"):
                            rungs[r["rung"]] += 1
                elif m == "mulliganKeepHand" and r.get("by") == "bridge":
                    mull[str(r.get("keep")).lower()] += 1

    out = {
        "runs": [str(r) for r in run_dirs],
        "games": games,
        "decisive": decisive,
        "draw_clock": draw_clock,
        "crashes": crashes,
        "turns_median": statistics.median(turns) if turns else None,
        "priority": dict(prio),
        "vetoes": dict(vetoes),
        "rungs": dict(rungs),
        "mulligan_keep": dict(mull),
    }
    n_veto = sum(vetoes.values())
    out["veto_rate"] = n_veto / max(prio["cast"] + n_veto, 1)
    if bridged_games:
        p = model_wins / bridged_games
        out["model_wins"] = model_wins
        out["winrate"] = p
        out["se"] = (p * (1 - p) / bridged_games) ** 0.5
    else:
        out["seat0_winrate"] = seat0_wins / max(decisive, 1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", required=True,
                    help="name=run_dir[,run_dir...]")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    report = {}
    for spec in args.arm:
        name, dirs = spec.split("=", 1)
        report[name] = aggregate([Path(d) for d in dirs.split(",")])
    Path(args.out).write_text(json.dumps(report, indent=1) + "\n")
    for name, a in report.items():
        wr = a.get("winrate")
        wr_s = f"winrate {wr:.4f} ± {a['se']:.4f}" if wr is not None else \
            f"seat0 {a.get('seat0_winrate'):.3f}"
        print(f"{name}: {a['games']} games, {a['decisive']} decisive, "
              f"{a['crashes']} crashes, {wr_s}, veto_rate {a['veto_rate']:.4f}, "
              f"rungs {a['rungs']}")


if __name__ == "__main__":
    main()
