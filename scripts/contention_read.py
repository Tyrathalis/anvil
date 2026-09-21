"""The contention smoke's read (09-21): did in-flight games survive a foreign GPU
job? For the given harness dirs: games by status, worker log lines naming a
bridge deadline / poison, per-game wall vs a reference smoke's, the run's
gpu-yield.json transitions. Usage: contention_read.py <arm dir>... [--ref <arm dir>...]"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import statistics
from pathlib import Path


def read(dirs: list[str]) -> dict:
    status = collections.Counter()
    ms = []
    deadline_lines = 0
    yields = []
    for d in dirs:
        for line in Path(d, "games.jsonl").read_text().splitlines():
            g = json.loads(line)
            status[g.get("status")] += 1
            if g.get("ms"):
                ms.append(g["ms"])
        for f in glob.glob(f"{d}/workers/inv-*/out.log"):
            for line in open(f, errors="replace"):
                if "deadline on" in line or "poison" in line.lower():
                    deadline_lines += 1
        y = Path(d, "gpu-yield.json")
        if y.exists():
            yields.append(json.loads(y.read_text()))
    return {
        "dirs": dirs, "games": sum(status.values()), "status": dict(status),
        "deadline_or_poison_lines": deadline_lines,
        "ms_median": statistics.median(ms) if ms else None,
        "ms_max": max(ms) if ms else None, "gpu_yield": yields,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--ref", nargs="*", default=[])
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    r = {"contention": read(a.dirs)}
    if a.ref:
        r["reference"] = read(a.ref)
    print(json.dumps(r, indent=2))
    if a.out:
        Path(a.out).write_text(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
