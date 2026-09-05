#!/usr/bin/env python3
"""M10 reset Fork 3 — the LABEL HARVEST: inline certification under ADVISORY
generation (the 2026-09-04 adjudication after the day-zero HALT: better
labels before any training — the planner is distilled from search-
adjudicated labels, then the day-zero read re-runs as the gate).

One run = N generation batches of the ckpt of record served SAMPLED at the
generation temperature (the loop's own state distribution; slot tokens fed
advisory, the cast head free), workers in rollout-label mode with -certify
<horizon>: at -points-sampled quiescent MAIN1 windows the worker asks the
server for arms (anvil.certify, --certify-rate = the accept gate) and rolls
NATURAL + arms x K to the horizon. After each batch: ingest the store,
finish the labels (scripts/sched_certify_finish.py) -> <store>/sched-labels
.jsonl (+ .spread.jsonl). The manifest lists every (labels, store) pair for
the distiller's --certified and the learner's --seed-labels/--seed-store.

Rate arithmetic (draft §D.3): ~4,000 eligible windows per 480 games; 2% ->
~80 labeled windows per batch at ~44 s lane time each (16 arms x K=8,
horizon 2), ~+20% wall. Workers at 4g (the mint's OOM class).

Usage:
  uv run python scripts/sched_harvest.py --name harvest1 \
      --ckpt data/training/d6-run11/iter-019/train/last.pt \
      --batches 4 --games 480 --certify-rate 0.05 [--horizon 2] [--rollout-k 8]
      [--points 15] [--workers 8] [--heap 4g] [--port 50071] [--seed-base N]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO / "data/runs"
TRAJ_DIR = REPO / "data/trajectories"


def _notify(title: str, msg: str) -> None:
    try:
        from anvil.training.notify import notify

        notify(title, msg)
    except Exception:  # noqa: BLE001
        pass


def _wait_port(port: int, proc: subprocess.Popen, timeout: float = 600.0) -> None:
    import socket

    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited {proc.returncode} before opening :{port}")
        with socket.socket() as s:
            s.settimeout(0.5)
            try:
                s.connect(("127.0.0.1", port))
                return
            except OSError:
                time.sleep(1.0)
    proc.kill()
    raise TimeoutError(f"server on :{port} never opened")


def start_server(a, out: Path) -> subprocess.Popen:
    cmd = [
        sys.executable, "-m", "anvil.bridge.server", "--mode", "model", "--ckpt", a.ckpt,
        "--port", str(a.port), "--pass-delta", "0",
        "--sample", "--temperature", str(a.temperature), "--mu-out", str(out / "serve-mu.jsonl"),
        "--fork-instrument",  # wire-only completions on a sampled server (the mint's mode)
        "--certify-rate", str(a.certify_rate), "--certify-salt", str(a.certify_salt),
        "--counts-out", str(out / "server.counts.json"),
    ]
    if a.sched_basis != "legal":
        cmd += ["--sched-basis", a.sched_basis]
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(cmd, stdout=open(out / "server.log", "a"), stderr=subprocess.STDOUT,
                            env=env, cwd=str(REPO))
    _wait_port(a.port, proc)
    return proc


def stop_server(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=90)
        except subprocess.TimeoutExpired:
            proc.kill()


def launch_batch(a, purpose: str, start_index: int) -> Path:
    before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
    cmd = [
        sys.executable, "-m", "anvil.bridge.harness", "launch", "--pool",
        "--games", str(a.games), "--games-per-pair", str(a.games_per_pair),
        "--start-index", str(start_index), "--workers", str(a.workers),
        "--chunk", str(max(1, min(a.chunk, a.games // a.workers or 1))),
        "--bridge", f"grpc:localhost:{a.port}", "--obs", "--census",
        "--purpose", purpose, "--seed-base", str(a.seed_base),
        "--rollout-k", str(a.rollout_k), "--rollout-points", str(a.points),
        "--certify", str(a.horizon), "--heap", a.heap,
    ]
    if a.reask:
        cmd.append("--reask")
    print(f"[harvest] launch: {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True, cwd=str(REPO))
    new = set(glob.glob(str(RUNS_DIR / f"{purpose}-*"))) - before
    if len(new) != 1:
        raise RuntimeError(f"expected one new run dir for {purpose}, got {new}")
    return Path(new.pop())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--ckpt", required=True, help="the ckpt served (advisory, sampled)")
    ap.add_argument("--batches", type=int, default=1)
    ap.add_argument("--games", type=int, default=480)
    ap.add_argument("--games-per-pair", type=int, default=2)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--chunk", type=int, default=30)
    ap.add_argument("--heap", default="4g")
    ap.add_argument("--port", type=int, default=50071)
    ap.add_argument("--seed-base", type=int, default=20520904)
    ap.add_argument("--start-index", type=int, default=0)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--reask", action="store_true", default=True)
    ap.add_argument("--no-reask", dest="reask", action="store_false")
    ap.add_argument("--sched-basis", choices=["legal", "hand"], default="legal")
    ap.add_argument("--certify-rate", type=float, default=0.02)
    ap.add_argument("--certify-salt", type=int, default=0)
    ap.add_argument("--horizon", type=int, default=2, help="rollout horizon in turns (0 = game end)")
    ap.add_argument("--rollout-k", type=int, default=8)
    ap.add_argument("--points", type=int, default=15, help="-points (candidate turns per game; 15 = every turn 2..16)")
    ap.add_argument("--era", default=None)
    ap.add_argument("--watchd", action="store_true")
    a = ap.parse_args()

    out = REPO / "data/runs" / f"sched-harvest-{a.name}"
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "harvest-manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {
        "name": a.name, "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "args": vars(a), "batches": []}
    era = a.era or f"inline-{a.name}"
    if a.watchd:
        subprocess.run([sys.executable, str(REPO / "scripts/anvil_watchd.py"), "register",
                        "--name", f"sched-harvest-{a.name}", "--pid", str(os.getpid()),
                        "--dir", str(out), "--stall-min", "90"], check=False)
    server = start_server(a, out)
    t0 = time.monotonic()
    try:
        done = len(manifest["batches"])
        for b in range(done, a.batches):
            purpose = f"sched-harvest-{a.name}-b{b:02d}"
            start = a.start_index + b * a.games
            tb = time.monotonic()
            run_dir = launch_batch(a, purpose, start)
            subprocess.run([sys.executable, "-m", "anvil.store", "ingest", str(run_dir)],
                           check=True, cwd=str(REPO))
            store = TRAJ_DIR / run_dir.name
            labels = store / "sched-labels.jsonl"
            fin = subprocess.run(
                [sys.executable, str(REPO / "scripts/sched_certify_finish.py"), "--run", str(run_dir),
                 "--store", str(store), "--out", str(labels), "--cert-ckpt", a.ckpt, "--era", era],
                check=True, cwd=str(REPO), capture_output=True, text=True)
            print(fin.stdout.strip(), flush=True)
            meta = json.loads(labels.read_text().splitlines()[0])
            manifest["batches"].append({
                "run": str(run_dir), "store": str(store), "labels": str(labels),
                "points": meta["points"], "labels_n": meta["labels"], "frame": meta["frame"],
                "wall_s": round(time.monotonic() - tb)})
            manifest["loader"] = {
                "seed_labels": ",".join(x["labels"] for x in manifest["batches"]),
                "seed_store": ",".join(x["store"] for x in manifest["batches"]),
                "total_labels": sum(x["labels_n"] for x in manifest["batches"]),
                "total_points": sum(x["points"] for x in manifest["batches"]),
            }
            manifest_path.write_text(json.dumps(manifest, indent=2))
            # heartbeat for the watcher + a progress row
            with open(out / "progress.jsonl", "a") as pf:
                pf.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "batch": b,
                                     "labels": meta["labels"], "points": meta["points"],
                                     "wall_s": round(time.monotonic() - tb)}) + "\n")
            print(f"[harvest] batch {b}: {meta['points']} points -> {meta['labels']} labels "
                  f"in {(time.monotonic() - tb) / 60:.1f} min", flush=True)
    finally:
        stop_server(server)
        if a.watchd:
            subprocess.run([sys.executable, str(REPO / "scripts/anvil_watchd.py"), "unregister",
                            "--name", f"sched-harvest-{a.name}"], check=False)
    ld = manifest.get("loader", {})
    _notify(f"sched harvest {a.name}: COMPLETE",
            f"{len(manifest['batches'])} batches, {ld.get('total_points')} points -> "
            f"{ld.get('total_labels')} labels; {(time.monotonic() - t0) / 3600:.1f} h")
    print(f"[harvest] done -> {manifest_path}\n  --seed-labels {ld.get('seed_labels')}\n"
          f"  --seed-store {ld.get('seed_store')}")


if __name__ == "__main__":
    main()
