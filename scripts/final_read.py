"""2,000-game Ante-corrected winrate read (the run-3/run-5 closeout
protocol, formalized): per seat assignment, 1,000 games (200 pairs x 5)
against the heuristic at argmax serve under -reask, then ingest + Ante
certify (full-vis critic) per run, then arms_report --ante.

Usage:
  uv run python scripts/final_read.py \
      --ckpt data/training/d6-run6/iter-019/train/last.pt \
      --name run6-final --port 50065
"""

from __future__ import annotations

import argparse
import glob
import subprocess
import sys
from pathlib import Path

from anvil.training.selfplay import RUNS_DIR, _run, _start_server, _stop_server

CRITIC = "data/training/d4-critic-fullvis/last.pt"
TRAJ_DIR = Path("data/trajectories")


def main() -> None:
    ap = argparse.ArgumentParser(description="2,000-game corrected read")
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--name", required=True, help="report prefix, e.g. run6-final")
    ap.add_argument("--games", type=int, default=1000, help="games per seat arm")
    ap.add_argument("--games-per-pair", type=int, default=5)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--chunk", type=int, default=50)
    ap.add_argument("--port", type=int, default=50065)
    ap.add_argument("--pairs-file",
                    default="data/runs/d5arm-d0-s0-20260714-143546/pairs.txt")
    ap.add_argument("--seed-base", type=int, default=20260710)
    ap.add_argument("--critic", default=CRITIC)
    a = ap.parse_args()

    # ---- generation: both seat assignments under one argmax server ----
    arm_dirs: list[Path] = []
    server = _start_server(a.ckpt, a.port,
                           RUNS_DIR / f"{a.name}-arm-server.log", sample=False)
    try:
        for seat in (0, 1):
            purpose = f"{a.name}arm-s{seat}"
            before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
            _run([sys.executable, "-m", "anvil.bridge.harness", "launch",
                  "--pairs-file", a.pairs_file, "--games", str(a.games),
                  "--games-per-pair", str(a.games_per_pair),
                  "--workers", str(a.workers), "--chunk", str(a.chunk),
                  "--bridge", f"grpc:localhost:{a.port}",
                  "--census", "--obs", "--purpose", purpose,
                  "--seed-base", str(a.seed_base),
                  "--bridge-seats", str(seat), "--reask"])
            new = set(glob.glob(str(RUNS_DIR / f"{purpose}-*"))) - before
            if len(new) != 1:
                raise RuntimeError(f"expected one new run dir, got {new}")
            arm_dirs.append(Path(new.pop()))
    finally:
        _stop_server(server)

    # ---- ingest + certify per run (certify needs a trajectory store) ----
    ante_reports: list[str] = []
    for rd in arm_dirs:
        _run([sys.executable, "-m", "anvil.store", "ingest", str(rd)])
        store = TRAJ_DIR / rd.name
        if not store.exists():
            raise RuntimeError(f"ingest did not produce {store}")
        rep = RUNS_DIR / f"ante-{rd.name}.json"
        _run([sys.executable, "-m", "anvil.ante.certify",
              "--store", str(store), "--ckpt", a.critic,
              "--out", str(rep), "--ledger-out", f"{rep}.ledger.jsonl"])
        ante_reports.append(str(rep))

    # ---- pooled report ----
    out = RUNS_DIR / f"{a.name}-arms-report.json"
    _run([sys.executable, "scripts/arms_report.py",
          "--arm", f"{a.name}={','.join(map(str, arm_dirs))}",
          "--ante", f"{a.name}={','.join(ante_reports)}",
          "--out", str(out)])
    print(f"[final_read] report: {out}")


if __name__ == "__main__":
    main()
