"""The fleet bench (the throughput week, 2026-09-14; m12-plan record 09-10
item 4): games per hour vs (workers, servers) on the saturating regime —
self-play, both seats network-played, the search directive at rate 1 with
rolls 2 (the h2 relabel's recipe that pinned one server at 110% CPU with
16 workers). Re-issues the Build 5 sizing line with servers as a variable.

Each cell: a fleet of S servers on consecutive ports -> one harness pool
launch of G games at W workers (chunk = ceil(G / W), one chunk per worker)
-> the fleet stopped -> a row: wall, g/h, the servers' occupancy from their
`[server] stats` lines (rps, mean batch, wait p90, busy %), crashes.

    uv run python scripts/fleet_bench.py --cells 8:1,16:1,16:2,24:3,32:4 --games 64

Rows land in data/runs/fleet-bench-<ts>/bench.md as they finish (the run is
resumable by cell: a cell whose row exists is skipped).
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

from anvil.bridge.fleet import bridge_addrs
from anvil.training.notify import notify, watch_register, watch_unregister
from anvil.training.selfplay import RUNS_DIR, _run, _start_server, _stop_server

STATS = re.compile(
    r"stats: (\d+) asks in [\d.]+s \((\d+) rps\), mean batch ([\d.]+), wait p50 ([\d.]+) / "
    r"p90 ([\d.]+) / p99 ([\d.]+) ms, forward ([\d.]+) ms/batch \((\d+)% busy\), queue max (\d+)"
)


def _server_occupancy(log: Path) -> dict:
    rows = [STATS.search(l) for l in log.read_text().splitlines()]
    rows = [m.groups() for m in rows if m and int(m.group(1)) > 50]  # drop idle/warm-up windows
    if not rows:
        return {}
    col = lambda i, f=float: [f(r[i]) for r in rows]
    return {
        "rps_per_server": statistics.mean(col(1)),
        "mean_batch": statistics.mean(col(2)),
        "wait_p90_ms": statistics.mean(col(4)),
        "busy_pct": statistics.mean(col(7)),
        "windows": len(rows),
    }


def _games(run_dir: Path) -> list[dict]:
    out = []
    for f in run_dir.glob("workers/inv-*/games.jsonl"):
        for line in f.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description="fleet bench: g/h vs (workers, servers)")
    ap.add_argument("--ckpt", default="data/training/m12-build3-e3/last.pt")
    ap.add_argument("--jar", required=True, help="the pinned jar snapshot")
    ap.add_argument("--cells", default="8:1,16:1,16:2,24:3,32:4", help="workers:servers, comma list")
    ap.add_argument("--games", type=int, default=64)
    ap.add_argument("--port", type=int, default=50090)
    ap.add_argument("--seed-base", type=int, default=20260914)
    ap.add_argument(
        "--forge-args",
        default="-search -searchrate 1 -searchrolls 2 -searchact 0.05 -searchtemp 0.025",
    )
    ap.add_argument("--name", default=None)
    a = ap.parse_args()

    name = a.name or f"fleet-bench-{time.strftime('%Y%m%d-%H%M%S')}"
    out = RUNS_DIR / name
    out.mkdir(parents=True, exist_ok=True)
    table = out / "bench.md"
    if not table.exists():
        table.write_text(
            f"# fleet bench {name}\n\nckpt `{a.ckpt}` jar `{a.jar}` games/cell {a.games} "
            f"forge args `{a.forge_args}` (both seats network-played)\n\n"
            "| workers | servers | games | wall min | g/h | rps/server | mean batch | wait p90 ms | busy % | crashes |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n"
        )
    watch_register(name, RUNS_DIR, stall_min=90)
    try:
        for cell in a.cells.split(","):
            w, s = (int(x) for x in cell.split(":"))
            tag = f"w{w}s{s}"
            if re.search(rf"^\| {w} \| {s} \|", table.read_text(), re.M):
                print(f"[bench] {tag} done already")
                continue
            print(f"[bench] cell {tag}: {s} server(s) on {a.port}.., {w} workers, {a.games} games")
            server = _start_server(
                a.ckpt, a.port, out / f"server-{tag}.log", sample=False, servers=s,
                sched_flags=["--stats-every", "30", "--counts-out", str(out / f"server-{tag}.counts.json")],
            )
            purpose = f"{name}-{tag}"
            before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
            t0 = time.monotonic()
            try:
                _run([
                    sys.executable, "-m", "anvil.bridge.harness", "launch", "--pool",
                    "--games", str(a.games), "--games-per-pair", "5",
                    "--workers", str(w), "--chunk", str(math.ceil(a.games / w)),
                    "--bridge", bridge_addrs(a.port, s), "--obs", "--census", "--labels",
                    "--purpose", purpose, "--seed-base", str(a.seed_base),
                    "--jar", a.jar, "--heap", "3g", f"--forge-args={a.forge_args}",
                ])
            except subprocess.CalledProcessError as e:
                print(f"[bench] {tag}: harness rc={e.returncode} (row still recorded)")
            finally:
                wall = time.monotonic() - t0
                _stop_server(server)
            new = sorted(set(glob.glob(str(RUNS_DIR / f"{purpose}-*"))) - before)
            games = _games(Path(new[-1])) if new else []
            done = len(games)
            crashes = sum(1 for g in games if str(g.get("status", "")).startswith("crash"))
            occ = _server_occupancy(out / f"server-{tag}.log")
            gh = done / wall * 3600 if wall else 0.0
            row = (
                f"| {w} | {s} | {done} | {wall / 60:.1f} | {gh:.0f} | "
                f"{occ.get('rps_per_server', 0):.0f} | {occ.get('mean_batch', 0):.2f} | "
                f"{occ.get('wait_p90_ms', 0):.1f} | {occ.get('busy_pct', 0):.0f} | {crashes} |\n"
            )
            with open(table, "a") as f:
                f.write(row)
            print(f"[bench] {tag}: {row.strip()}")
        notify(f"anvil fleet bench DONE", str(table), tag="fleet")
    except BaseException as e:  # noqa: BLE001 — the notify is the point
        notify(f"anvil fleet bench FAILED", f"{type(e).__name__}: {e} — see {out}", tag="fleet")
        raise
    finally:
        watch_unregister(name)


if __name__ == "__main__":
    main()
