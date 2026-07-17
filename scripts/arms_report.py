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
    reask_env = False  # any run under -reask (environment provenance)
    reask_rescued = 0  # casts realized on a re-ask attempt (would've passed)
    turns = []
    prio = Counter()
    rungs = Counter()
    vetoes = Counter()
    mull = Counter()

    for rd in run_dirs:
        # NB: in pure-heuristic runs every seat is named "Anvil(n)-deck";
        # only bridged runs name the non-bridged seat "Heur(n)". The bridged
        # seat must come from run.json, never from winner-string sniffing.
        run_manifest = json.loads((rd / "run.json").read_text())
        bridged = run_manifest.get("bridge_seats") is not None
        reask_env = reask_env or bool(run_manifest.get("reask"))
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
                        if not r.get("reask"):
                            prio["first_veto"] += 1
                    elif r.get("pick") == "pass":
                        prio["pass"] += 1
                    else:
                        prio["cast"] += 1
                        if r.get("rung"):
                            rungs[r["rung"]] += 1
                        if r.get("reask"):
                            reask_rescued += 1
                        else:
                            prio["first_cast"] += 1
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
    # M3 D1: chain-independent basis (one first attempt per window; census
    # "reask" marks attempts > 0 only) — comparable across reask on/off envs
    out["first_veto_rate"] = prio["first_veto"] / max(
        prio["first_veto"] + prio["first_cast"], 1)
    out["reask"] = reask_env
    if reask_env:
        # rescue rate = vetoed cast intents eventually realized in-window
        out["reask_rescued"] = reask_rescued
        out["reask_rescue_rate"] = reask_rescued / max(n_veto, 1)
    if bridged_games:
        p = model_wins / bridged_games
        out["model_wins"] = model_wins
        out["winrate"] = p
        out["se"] = (p * (1 - p) / bridged_games) ** 0.5
    else:
        out["seat0_winrate"] = seat0_wins / max(decisive, 1)
    return out


def merge_ante(arm: dict, run_dirs: list[Path], reports: list[Path]) -> None:
    """Fold anvil.ante.certify reports (one per mirrored run) into the arm as
    a corrected model winrate. Certify's raw/corrected are SEAT-0-signed;
    the model seat comes from each run's bridge_seats, so the s1-mirrored
    run's read is flipped. Reports are matched to run dirs by store name
    (ingest names the store after the run dir)."""
    by_store = {}
    for p in reports:
        rep = json.loads(p.read_text())
        by_store[Path(rep.get("store", "")).name] = rep
    per_run = []
    for rd in run_dirs:
        rep = by_store.get(rd.name)
        if rep is None:
            raise SystemExit(f"--ante: no certify report for run {rd.name} "
                             f"(have {sorted(by_store)})")
        seats = str(json.loads((rd / "run.json").read_text()).get("bridge_seats"))
        if seats not in ("0", "1"):
            raise SystemExit(f"--ante: run {rd.name} has bridge_seats={seats}; "
                             "corrected arms need single-seat mirrored runs")
        flip = seats == "1"
        wr = rep["corrected_cv_winrate"]
        raw = rep["raw_winrate"]
        per_run.append({
            "run": rd.name, "model_seat": int(seats), "games": rep["games"],
            "raw_winrate": round(1 - raw, 4) if flip else raw,
            "corrected_winrate": round(1 - wr, 4) if flip else wr,
            "corrected_se": rep["corrected_cv_se"],
            "var_ratio_cv": rep.get("var_ratio_cv"),
        })
    n_total = sum(r["games"] for r in per_run)
    pooled = sum(r["corrected_winrate"] * r["games"] for r in per_run) / n_total
    pooled_se = (sum((r["games"] / n_total) ** 2 * r["corrected_se"] ** 2
                     for r in per_run)) ** 0.5
    arm["ante"] = {
        "corrected_winrate": round(pooled, 4),
        "corrected_se": round(pooled_se, 4),
        "games": n_total,
        "per_run": per_run,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", required=True,
                    help="name=run_dir[,run_dir...]")
    ap.add_argument("--ante", action="append", default=[],
                    help="name=certify_report.json[,...] — Ante-ledger corrected "
                         "winrate for the same arm (one report per mirrored run; "
                         "matched to run dirs by store name)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    report = {}
    arm_dirs = {}
    for spec in args.arm:
        name, dirs = spec.split("=", 1)
        arm_dirs[name] = [Path(d) for d in dirs.split(",")]
        report[name] = aggregate(arm_dirs[name])
    for spec in args.ante:
        name, paths = spec.split("=", 1)
        if name not in report:
            raise SystemExit(f"--ante arm '{name}' has no matching --arm")
        merge_ante(report[name], arm_dirs[name], [Path(p) for p in paths.split(",")])
    Path(args.out).write_text(json.dumps(report, indent=1) + "\n")
    for name, a in report.items():
        wr = a.get("winrate")
        wr_s = f"winrate {wr:.4f} ± {a['se']:.4f}" if wr is not None else \
            f"seat0 {a.get('seat0_winrate'):.3f}"
        if a.get("ante"):
            wr_s += (f", ante-corrected {a['ante']['corrected_winrate']:.4f} "
                     f"± {a['ante']['corrected_se']:.4f}")
        print(f"{name}: {a['games']} games, {a['decisive']} decisive, "
              f"{a['crashes']} crashes, {wr_s}, veto_rate {a['veto_rate']:.4f} "
              f"(first-attempt {a['first_veto_rate']:.4f}), rungs {a['rungs']}")


if __name__ == "__main__":
    main()
