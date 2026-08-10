"""Cycle curation stock: fresh iter-019 mainlines -> rank-critic traces
-> calibrated curation (M6 graduated cycle, user-approved 2026-08-08).

The critic asset (rank-critic-c2v3) trained on rollout labels drawn from
every existing iter-019 game population — so honest curation stock must
be games the critic has never seen labels from. Fresh seed base, standing
generation recipe, traced with the NEW critic + its era-scoped isotonic
map (calibrated curation is this cycle's design intent; the raw-vs-
calibrated population question was settled by the migration read:
calibrated keeps 45% addressable under the rank critic).

Usage:
  uv run python scripts/cycle_stock.py [--games-per-arm 800] [--workers 16]
"""

from __future__ import annotations

import argparse
import glob
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from anvil.training.notify import notify
from anvil.training.selfplay import RUNS_DIR, _start_server, _stop_server, batch_chunk

POLICY = "data/training/d6-run11/iter-019/train/last.pt"
RANK_CRITIC = "data/training/rank-critic-c2v3/last.pt"
ISO_MAPS = "data/runs/isotonic-maps/isotonic-maps-rank-critic-v1.json"
SEED_BASE = 20260809
PORT = 50073
TRACE_OUT = "data/runs/early-doom-cycle3-rankcrit"


def _run(cmd: list[str]) -> None:
    import subprocess

    print(f"[stock] $ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--games-per-arm", type=int, default=800)
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    t0 = time.time()
    try:
        log = Path(ROOT / TRACE_OUT).with_suffix(".server.log")
        log.parent.mkdir(parents=True, exist_ok=True)
        server = _start_server(POLICY, PORT, log, sample=False)
        run_dirs = []
        try:
            for seat in (0, 1):
                purpose = f"cycle3-s{seat}"
                before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
                _run(
                    [
                        sys.executable,
                        "-m",
                        "anvil.bridge.harness",
                        "launch",
                        "--pool",
                        "--games",
                        str(a.games_per_arm),
                        "--games-per-pair",
                        "5",
                        "--workers",
                        str(a.workers),
                        "--chunk",
                        str(batch_chunk(a.games_per_arm, a.workers, 30)),
                        "--bridge",
                        f"grpc:localhost:{PORT}",
                        "--obs",
                        "--census",
                        "--reask",
                        "--bridge-seats",
                        str(seat),
                        "--purpose",
                        purpose,
                        "--seed-base",
                        str(SEED_BASE),
                    ]
                )
                new = set(glob.glob(str(RUNS_DIR / f"{purpose}-*"))) - before
                if len(new) != 1:
                    raise RuntimeError(f"expected one run dir: {new}")
                run_dirs.append(Path(new.pop()))
        finally:
            _stop_server(server)
        stores = []
        for rd in run_dirs:
            _run([sys.executable, "-m", "anvil.store", "ingest", str(rd)])
            stores.append(f"data/trajectories/{rd.name}")
        cmd = [
            sys.executable,
            "scripts/early_doom.py",
            "trace",
            "--ckpt",
            RANK_CRITIC,
            "--out",
            TRACE_OUT,
        ]
        for i, s in enumerate(stores):
            cmd += ["--arm", f"{s}:{i}"]
        _run(cmd)
        _run(
            [
                sys.executable,
                "scripts/early_doom.py",
                "analyze",
                "--out",
                TRACE_OUT,
                "--isotonic",
                ISO_MAPS,
                "--isotonic-key",
                "c2/v_rank",
            ]
        )
        import json

        s = json.loads((ROOT / TRACE_OUT / "summary.json").read_text())
        wall_h = (time.time() - t0) / 3600
        notify(
            "cycle stock done",
            f"{s['games']} games, {s['addressable_losses']} addressable "
            f"({s['addressable_loss_frac']:.0%} of losses) in "
            f"{wall_h:.1f}h -> {TRACE_OUT}",
        )
        print(f"[stock] DONE in {wall_h:.1f}h")
    except BaseException as e:
        notify("cycle stock FAILED", f"{type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()
