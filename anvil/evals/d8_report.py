"""D8 arm report: winrates vs heuristic + executor telemetry (M1 D8).

  uv run python -m anvil.evals.d8_report data/runs/d8arm-heur-* \\
      --model d0=data/runs/d8arm-d0-s0-*,data/runs/d8arm-d0-s1-* \\
      --model dc=data/runs/d8arm-dc-s0-*,data/runs/d8arm-dc-s1-*

Each model arm is two mirrored half-runs (same seeds, bridged seat 0 then 1),
so every held-out pair is played from both sides. Winrate is recorded, not
gated (m1-bc-plan D8). The census aggregates decompose the executor: veto
reasons, disambiguation rungs, one-shot cast counts.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
from collections import Counter
from pathlib import Path


def _games(run_dir: Path) -> list[dict]:
    return [json.loads(l) for l in open(run_dir / "games.jsonl")]


def _census(run_dir: Path):
    for f in glob.glob(str(run_dir / "workers" / "*" / "census.jsonl")):
        for l in open(f):
            yield json.loads(l)


def _wall_s(run_dir: Path) -> float:
    s = json.loads((run_dir / "summary.json").read_text()) \
        if (run_dir / "summary.json").exists() else {}
    if "wall_s" in s:
        return s["wall_s"]
    return sum(g.get("ms", 0) for g in _games(run_dir)) / 1000  # serial lower bound


def arm_stats(runs: list[Path], model_prefix: str = "Anvil(") -> dict:
    games, census_prio, census_mull = [], Counter(), Counter()
    rungs, vetoes = Counter(), Counter()
    for rd in runs:
        games.extend(_games(rd))
        for r in _census(rd):
            if r.get("m") == "chooseSpellAbilityToPlay" and r.get("by") == "bridge":
                if r.get("veto"):
                    vetoes[r["veto"]] += 1
                elif r.get("pick") == "pass":
                    census_prio["pass"] += 1
                else:
                    census_prio["cast"] += 1
                    rungs[r.get("rung", "?")] += 1
            elif r.get("m") == "mulliganKeepHand" and "keep" in r:
                census_mull[r["keep"]] += 1
    n = len(games)
    wins = sum(1 for g in games
               if g.get("winner") and g["winner"].startswith(model_prefix))
    decisive = sum(1 for g in games if g.get("status") == "won")
    p = wins / max(n, 1)
    return {
        "runs": [str(r) for r in runs], "games": n,
        "model_wins": wins, "winrate": p,
        "se": math.sqrt(p * (1 - p) / max(n, 1)),
        "decisive": decisive,
        "draw_clock": sum(bool(g.get("draw_clock")) for g in games),
        "crashes": sum("crash" in (g.get("status") or "") for g in games),
        "turns_median": sorted(g["turns"] for g in games)[n // 2] if n else None,
        "priority": dict(census_prio), "vetoes": dict(vetoes),
        "rungs": dict(rungs), "mulligan_keep": dict(census_mull),
        "veto_rate": (sum(vetoes.values())
                      / max(sum(vetoes.values()) + census_prio.get("cast", 0), 1)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline", help="heuristic arm run dir (glob ok)")
    ap.add_argument("--model", action="append", default=[],
                    help="name=run_dir[,run_dir...] (globs ok); repeatable")
    ap.add_argument("--out", default=None, help="also write JSON here")
    a = ap.parse_args()

    def expand(pat: str) -> list[Path]:
        hits = sorted(glob.glob(pat))
        if not hits:
            raise SystemExit(f"no runs match {pat!r}")
        return [Path(h) for h in hits]

    report = {}
    base_runs = expand(a.baseline)
    report["heuristic"] = arm_stats(base_runs)
    # baseline is heuristic-vs-heuristic: "winrate" counts Anvil( prefixes,
    # which don't exist there — report seat-0 winrate instead for the prior
    base_games = [g for rd in base_runs for g in _games(rd)]
    seat0 = sum(1 for g in base_games
                if g.get("winner") and "(1)-" in g["winner"]) / max(len(base_games), 1)
    report["heuristic"]["seat0_winrate"] = seat0
    del report["heuristic"]["model_wins"], report["heuristic"]["winrate"], report["heuristic"]["se"]

    for spec in a.model:
        name, _, pats = spec.partition("=")
        runs = [p for pat in pats.split(",") for p in expand(pat)]
        report[name] = arm_stats(runs)

    for name, r in report.items():
        print(f"\n=== {name} ===")
        for k, v in r.items():
            if k != "runs":
                print(f"  {k}: {v}")
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=1) + "\n")
        print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
