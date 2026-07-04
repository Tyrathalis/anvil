#!/usr/bin/env python3
"""Callback census over the DC pool: many deck pairs, few games each.

The precon census (docs/design/callback-census-results.md) fixed the traffic
ranks on one deck pair; this driver re-runs it across the pool so the
64-silent-method list and the near-silent tags get their real-pool numbers.

Schedule: deterministic from the pool manifest — decks sorted by id, seeded
shuffles, consecutive pairing; repeated shuffle passes until --pairs is met,
so every deck appears at least once (default 100 pairs x 5 games = 500 games,
the original census volume). One `forge census` invocation per pair, W
sequential lanes. Census counts frequencies, not timing, so this runs nice-19
in the background — not a calibrated measurement.

Usage: uv run python scripts/census/run_dc_census.py [--pairs 100]
         [--games-per-pair 5] [--workers 4] [--seed-base 20260704]
Decks must be installed first: uv run python -m anvil.pool install
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parents[2]
sys.path.insert(0, str(REPO))

from anvil.pool import FORGE_DIR, POOL_DIR  # noqa: E402

FORGE_GUI_DIR = FORGE_DIR / "forge-gui"


def latest_manifest() -> dict:
    manifests = sorted(POOL_DIR.glob("pool-*.json"), key=lambda p: p.stat().st_mtime)
    if not manifests:
        sys.exit("no pool manifest — run `python -m anvil.pool build` first")
    return json.loads(manifests[-1].read_text())


def pair_schedule(deck_files: list[str], n_pairs: int, seed: int) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    rng = random.Random(seed)
    passno = 0
    while len(pairs) < n_pairs:
        order = sorted(deck_files)
        rng.shuffle(order)
        it = iter(order)
        for a, b in zip(it, it):
            pairs.append((a, b))
        passno += 1
        if passno > 100:
            sys.exit("cannot satisfy --pairs from this deck list")
    return pairs[:n_pairs]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--pairs", type=int, default=100)
    p.add_argument("--games-per-pair", type=int, default=5)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--seed-base", type=int, default=20260704)
    p.add_argument("--out", type=Path,
                   default=REPO / f"data/census/run-{_dt.date.today().strftime('%Y%m%d')}-dcpool")
    a = p.parse_args()
    a.out = a.out.resolve()  # lanes run with cwd=FORGE_GUI_DIR; relative paths are the known trap

    manifest = latest_manifest()
    jar = sorted((FORGE_DIR / "forge-gui-desktop/target").glob("*-jar-with-dependencies.jar"))[-1]
    a.out.mkdir(parents=True, exist_ok=True)

    pairs = pair_schedule([d["file"] for d in manifest["decks"]], a.pairs, a.seed_base)
    run_meta = {
        "pool_version": manifest["pool_version"],
        "fork_commit": subprocess.run(["git", "-C", str(FORGE_DIR), "rev-parse", "HEAD"],
                                      capture_output=True, text=True, check=True).stdout.strip(),
        "jar_sha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
        "pairs": pairs, "games_per_pair": a.games_per_pair,
        "seed_base": a.seed_base, "workers": a.workers,
    }
    (a.out / "run.json").write_text(json.dumps(run_meta, indent=2))

    # W sequential lanes over the pair list; each pair is one census invocation
    lanes: list[subprocess.Popen] = []
    for w in range(a.workers):
        script_lines = []
        for i in range(w, len(pairs), a.workers):
            d1, d2 = pairs[i]
            out = a.out / f"pair-{i:03d}.jsonl"
            if out.exists():  # crude resume: skip finished pairs on relaunch
                continue
            seed = a.seed_base + 1000 * i
            script_lines.append(
                f"nice -n 19 java -Xms1g -Xmx2g -XX:ActiveProcessorCount=2 "
                f"-jar '{jar}' census -d '{d1}' '{d2}' -f Commander "
                f"-n {a.games_per_pair} -s {seed} -o '{out}.tmp' "
                f"&& mv '{out}.tmp' '{out}'")
        lane_sh = a.out / f"lane-{w}.sh"
        lane_sh.write_text("#!/bin/sh\nset -e\n" + "\n".join(script_lines) + "\n")
        lane_sh.chmod(0o755)
        log = open(a.out / f"lane-{w}.log", "a")
        lanes.append(subprocess.Popen(["sh", str(lane_sh)], cwd=FORGE_GUI_DIR,
                                      stdout=log, stderr=subprocess.STDOUT))
    print(f"{len(pairs)} pairs x {a.games_per_pair} games, {a.workers} lanes -> {a.out}")
    rcs = [lane.wait() for lane in lanes]
    print(f"lanes done, exit codes {rcs}")
    if any(rcs):
        sys.exit(1)


if __name__ == "__main__":
    main()
