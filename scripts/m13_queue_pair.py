"""M13 Build 2's paired cell: the same seeds through per-batch launches
(`cells`) and through the shared queue (`one`) give the same games.

Layer `heur` (the proof): one iteration's batch plan (`iteration_batches`
with the Monte Carlo share) played with heuristic seats only, so nothing a
server does enters a game. The Monte Carlo batches run the count budget,
which is reproducible. Every game row must match.

Layer `mcjar`: the Monte Carlo batches alone on two jars (the pin's and a
candidate's) through the queue; ADR-0025's proof for a change on the Monte
Carlo path, which the standing forkcheck does not play.

`compare` reads any two sets of run dirs.

Usage:
  uv run python scripts/m13_queue_pair.py heur --name b2pair --games 480 --jar <jar>
  uv run python scripts/m13_queue_pair.py mcjar --name b2mc --games 96 --jar <pin jar> --jar-b <candidate jar>
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from pathlib import Path

from anvil.training.selfplay import (
    MC_PROPS,
    RUNS_DIR,
    _new_run_dir,
    _run,
    batch_chunk,
    is_mc_batch,
    iteration_batches,
    launch_queue,
    queue_order,
)

KEYS = ("seed", "status", "winner", "turns", "windows", "first", "cap", "draw_clock", "decks", "profiles")


def rows(run_dir: Path) -> dict[int, dict]:
    return {r["i"]: r for r in map(json.loads, (run_dir / "games.jsonl").read_text().splitlines())}


def compare(a_dirs: list[Path], b_dirs: list[Path]) -> dict:
    """Per-game agreement of two sets of run dirs, paired in order."""
    out = {"games": 0, "identical": 0, "missing": 0, "differ": []}
    for da, db in zip(a_dirs, b_dirs):
        ra, rb = rows(da), rows(db)
        for i in sorted(set(ra) | set(rb)):
            if i not in ra or i not in rb:
                out["missing"] += 1
                continue
            out["games"] += 1
            diff = [k for k in KEYS if ra[i].get(k) != rb[i].get(k)]
            if diff:
                out["differ"].append({"a": da.name, "b": db.name, "i": i, "keys": diff})
            else:
                out["identical"] += 1
    return out


def flags(a, purpose: str, mc: bool, n: int, off: int, seat: "int | None", jar: str) -> list[str]:
    """One heuristic-seats batch: no seat is bridged; a Monte Carlo batch
    gives the mode to the seat opposite the one the network would hold."""
    argv = [
        "--pool", "--games", str(n), "--games-per-pair", "2", "--start-index", str(off),
        "--workers", str(a.workers), "--chunk", str(batch_chunk(n, a.workers, a.chunk)),
        "--bridge", "local-random", "--bridge-seats", "2", "--obs", "--census",
        "--purpose", purpose, "--seed-base", str(a.seed_base), "--jar", jar,
    ]
    if mc:
        argv += [f"--forge-args=-mc on -mcseats {1 - seat} -mcprops {MC_PROPS}", "--heap", a.mc_heap]
    return argv


def play(a, tag: str, batches: list, mode: str, jar: str) -> tuple[list[Path], float]:
    """The plan's batches under purposes `<name>-<tag><suffix>`, as cells or as one queue."""
    members = []
    for plan_purpose, n, off, seat in batches:
        purpose = f"{a.name}-{tag}{plan_purpose[len('x-i000'):]}"
        members.append((purpose, flags(a, purpose, is_mc_batch(plan_purpose), n, off, seat, jar)))
    t0 = time.monotonic()
    dirs: list = [None] * len(batches)
    if mode == "one":
        order = queue_order(batches, max(1, a.workers // 8))
        got = launch_queue(f"{a.name}-{tag}-q", a.workers, [(*members[j], cap) for j, cap in order])
        for (j, _), rd in zip(order, got):
            dirs[j] = rd
    else:
        for j, (purpose, argv) in enumerate(members):
            before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
            _run([sys.executable, "-m", "anvil.bridge.harness", "launch", *argv])
            dirs[j] = _new_run_dir(purpose, before)
    return dirs, time.monotonic() - t0


def mc_leaks(dirs: list[Path]) -> dict:
    """The workers' `mc_leaks N of M` tally lines, summed."""
    n_leak = n_cmp = 0
    for d in dirs:
        for log in d.glob("workers/inv-*/out.log"):
            for line in log.read_text(errors="replace").splitlines():
                if line.startswith("mc_leaks"):
                    parts = line.split()
                    n_leak += int(parts[1])
                    n_cmp += int(parts[3])
    return {"leaks": n_leak, "comparisons": n_cmp}


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("layer", choices=["heur", "mcjar"])
    ap.add_argument("--name", required=True)
    ap.add_argument("--games", type=int, default=480)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--chunk", type=int, default=30)
    ap.add_argument("--seed-base", type=int, default=20261120)
    ap.add_argument("--heur-frac", type=float, default=0.5)
    ap.add_argument("--mc-frac", type=float, default=0.1)
    ap.add_argument("--mc-heap", default="3g")
    ap.add_argument("--jar", required=True)
    ap.add_argument("--jar-b", default=None, help="mcjar: the candidate jar")
    a = ap.parse_args()
    out = RUNS_DIR / f"{a.name}-pair.json"

    if a.layer == "heur":
        batches = iteration_batches("x", 0, a.games, a.heur_frac, a.mc_frac)
        cells, wall_c = play(a, "cells", batches, "cells", a.jar)
        one, wall_o = play(a, "one", batches, "one", a.jar)
        rep = {"layer": "heur", "jar": a.jar, "plan": batches,
               "cells": {"wall_s": round(wall_c, 1), "dirs": [d.name for d in cells], "mc_leaks": mc_leaks(cells)},
               "one": {"wall_s": round(wall_o, 1), "dirs": [d.name for d in one], "mc_leaks": mc_leaks(one)},
               "compare": compare(cells, one)}
    else:
        if not a.jar_b:
            ap.error("mcjar needs --jar-b")
        n = a.games // 2
        batches = [("x-i000m0", n, 0, 0), ("x-i000m1", a.games - n, n, 1)]
        dirs = {tag: play(a, tag, batches, "one", jar)[0] for tag, jar in (("a", a.jar), ("b", a.jar_b))}
        rep = {"layer": "mcjar", "jar_a": a.jar, "jar_b": a.jar_b,
               "dirs": {t: [d.name for d in v] for t, v in dirs.items()},
               "mc_leaks": {t: mc_leaks(v) for t, v in dirs.items()}, "compare": compare(dirs["a"], dirs["b"])}
    out.write_text(json.dumps(rep, indent=1) + "\n")
    c = rep["compare"]
    print(f"[pair] {a.layer}: {c['identical']} of {c['games']} games identical, {len(c['differ'])} differ, "
          f"{c['missing']} missing from one side; report {out}")


if __name__ == "__main__":
    main()
