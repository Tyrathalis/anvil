"""M6 tranche component B: fresh-game diversity for the extended ranking
curve (ADR-0039 procedure; staged 2026-08-06 after component A's curve
flattened at 0.44-0.46 on re-used games).

The component-A confound: the offset tranche re-visits the same ~550
curated games, so a flat curve can mean game-saturation instead of
feature truncation. This driver adds era-clean game diversity — fresh
iter-019 mainlines through the UNCHANGED standing pipeline:

  1. generate  two eval-style arms (model seat 0/1 vs heuristic, argmax
               iter-019, --pool, fresh seed base) — the finalarm
               population recipe
  2. ingest    both run dirs -> trajectory stores
  3. trace     early_doom on both stores x both critics (era critic for
               curation + v_era; d4 for v_d4), then analyze -> fresh
               curation.jsonl (same addressable-loss filter)
  4. drill     grindstone map at crash:0 over the fresh curation, then
               drill_sweep arms o2:crash:-2,o4:crash:-4 (mix mirrors the
               banked map+sweep shape)

Labels land under drill-map-r11i019ext-k8 + drill-tranche-c2-fresh/arm-*;
the extended-dataset builder joins them the same way as component A.

Usage:
  uv run python scripts/tranche_b.py [--games-per-arm 800] [--smoke]
"""

from __future__ import annotations

import argparse
import glob
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from anvil.training.notify import notify
from anvil.training.selfplay import RUNS_DIR, _start_server, _stop_server, batch_chunk

POLICY = "data/training/d6-run11/iter-019/train/last.pt"
ERA_CRITIC = "data/training/d6-run11/iter-019/critic/last.pt"
D4_CRITIC = "data/training/d4-critic-fullvis/last.pt"
SEED_BASE = 20260806
PORT = 50069
MAP_OUT = "data/runs/drill-map-r11i019ext-k8"
SWEEP_OUT = "data/runs/drill-tranche-c2-fresh"
TRACE_ERA = "data/runs/early-doom-run11-i019-ext"
TRACE_D4 = "data/runs/early-doom-run11-d4crit-ext"


def _run(cmd: list[str]) -> None:
    print(f"[tranche-b] $ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def _launch_arm(seat: int, games: int, workers: int) -> Path:
    purpose = f"c2ext-s{seat}"
    before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
    _run(
        [
            sys.executable,
            "-m",
            "anvil.bridge.harness",
            "launch",
            "--pool",
            "--games",
            str(games),
            "--games-per-pair",
            "5",
            "--workers",
            str(workers),
            "--chunk",
            str(batch_chunk(games, workers, 30)),
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
        raise RuntimeError(f"expected one new run dir for {purpose}: {new}")
    return Path(new.pop())


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--games-per-arm", type=int, default=800)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--smoke", action="store_true", help="16 games/arm, map limit 8, no sweep arms")
    a = ap.parse_args()
    games = 16 if a.smoke else a.games_per_arm
    t0 = time.time()

    try:
        # ---- 1. generation (argmax policy serve) ----
        log = Path(SWEEP_OUT + ".server.log")
        log.parent.mkdir(parents=True, exist_ok=True)
        server = _start_server(POLICY, PORT, log, sample=False)
        try:
            run_dirs = [_launch_arm(0, games, a.workers), _launch_arm(1, games, a.workers)]
        finally:
            _stop_server(server)

        # ---- 2. ingest ----
        stores = []
        for rd in run_dirs:
            _run([sys.executable, "-m", "anvil.store", "ingest", str(rd)])
            store = ROOT / "data" / "trajectories" / rd.name
            if not store.exists():
                raise RuntimeError(f"ingest did not produce {store}")
            stores.append(store)

        # ---- 3. early-doom traces (era critic -> curation; d4 for v_d4) ----
        arms = [f"{s}:{i}" for i, s in enumerate(stores)]
        for ckpt, out in ((ERA_CRITIC, TRACE_ERA), (D4_CRITIC, TRACE_D4)):
            cmd = [sys.executable, "scripts/early_doom.py", "trace", "--ckpt", ckpt, "--out", out]
            for arm in arms:
                cmd += ["--arm", arm]
            _run(cmd)
        _run([sys.executable, "scripts/early_doom.py", "analyze", "--out", TRACE_ERA])

        # ---- 4. drill map at crash:0 + offset arms ----
        _run(
            [
                sys.executable,
                "-m",
                "anvil.grindstone",
                "plan",
                "--curation",
                f"{TRACE_ERA}/curation.jsonl",
                "--out",
                MAP_OUT,
                "--ckpt",
                POLICY,
                "--k",
                "8",
                "--anchor",
                "crash",
                "--turn-offset",
                "0",
            ]
            + (["--limit", "8"] if a.smoke else [])
        )
        _run(
            [
                sys.executable,
                "-m",
                "anvil.grindstone",
                "generate",
                "--manifest",
                MAP_OUT,
                "--port",
                str(PORT),
                "--workers",
                str(a.workers),
                "--chunk",
                "17",
                "--drill-stop",
            ]
        )
        _run([sys.executable, "-m", "anvil.grindstone", "report", "--manifest", MAP_OUT])
        if not a.smoke:
            _run(
                [
                    sys.executable,
                    "scripts/drill_sweep.py",
                    "--map",
                    MAP_OUT,
                    "--bins",
                    "lost,long_shot,coin,winnable",
                    "--arms",
                    "o2:crash:-2,o4:crash:-4",
                    "--out",
                    SWEEP_OUT,
                    "--workers",
                    str(a.workers),
                    "--chunk",
                    "17",
                    "--port",
                    str(PORT),
                ]
            )

        n = 0
        for f in glob.glob(f"{MAP_OUT}/drills.jsonl"):
            with open(f) as fh:
                n += sum(1 for _ in fh)
        wall_h = (time.time() - t0) / 3600
        print(f"[tranche-b] DONE: map {n} labels + sweep arms in {wall_h:.1f}h")
        notify("tranche B done", f"fresh-game labels banked (map {n} + arms) in {wall_h:.1f}h")
    except BaseException as e:
        notify("tranche B FAILED", f"{type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()
