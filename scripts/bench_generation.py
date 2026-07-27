"""Generation throughput arm: does raising worker count past 8 still buy games?

Generation was ~38% of a run's wall clock; since the learner's worker-side
collate landed (2026-07-26) the train phase is ~2.5h against generation's
~10h, so generation is now ~80% of a run and the next speedup, if any, is
here. The standing number is 1,146 g/h at w=8 both-seats under GPU
micro-batching (`d6-fleet-throughput-20260714-184530`) — measured on the
PRE-REBASE engine, so it is not comparable to what this script produces; the
arms here are only comparable to each other.

Config mirrors the RL loop's generation exactly: `--pool`, both seats
model-driven, sampling server at tau=1 writing mu records, `-reask`, obs +
census on. Chunk is sized so the chunk count divides evenly by every worker
count under test — otherwise a trailing partial round penalises whichever
arm happens not to divide, which looks exactly like a throughput difference.

Caveat when reading the result: chunk size CAPS parallelism. With the
driver's default chunk 30 and 480 games/iteration there are only 16 chunks,
so a worker count above 16 cannot help no matter what the GPU can serve.

Usage: uv run python scripts/bench_generation.py [--games 240] [--workers 8,16]
"""
from __future__ import annotations

import argparse
import glob
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from anvil.training.notify import notify  # noqa: E402
from anvil.training.selfplay import (RUNS_DIR, _start_server,  # noqa: E402
                                     _stop_server)

CKPT = "data/training/d6-run7b/iter-014/train/last.pt"


def arm(workers: int, games: int, chunk: int, gpp: int, port: int,
        seed_base: int) -> dict:
    purpose = f"genbench-w{workers}"
    before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
    cmd = [sys.executable, "-m", "anvil.bridge.harness", "launch", "--pool",
           "--games", str(games), "--games-per-pair", str(gpp),
           "--workers", str(workers), "--chunk", str(chunk),
           "--bridge", f"grpc:localhost:{port}",
           "--obs", "--census", "--reask",
           "--purpose", purpose, "--seed-base", str(seed_base)]
    t0 = time.monotonic()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    elapsed = time.monotonic() - t0
    if p.returncode != 0:
        return {"workers": workers, "ok": False,
                "error": (p.stderr or p.stdout)[-1200:]}

    new = set(glob.glob(str(RUNS_DIR / f"{purpose}-*"))) - before
    rd = Path(new.pop()) if len(new) == 1 else None
    decisive = crashed = 0
    if rd is not None and (rd / "games.jsonl").exists():
        for line in open(rd / "games.jsonl"):
            r = json.loads(line)
            if r.get("status") == "won":
                decisive += 1
            else:
                crashed += 1
    return {"workers": workers, "ok": True, "elapsed_s": round(elapsed, 1),
            "games": games, "games_per_hour": round(games / elapsed * 3600, 1),
            "decisive": decisive, "nondecisive": crashed,
            "run_dir": str(rd) if rd else None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=240)
    ap.add_argument("--workers", default="8,16")
    ap.add_argument("--games-per-pair", type=int, default=5)
    ap.add_argument("--port", type=int, default=50068)
    ap.add_argument("--seed-base", type=int, default=20260726)
    ap.add_argument("--out", default="data/runs/generation-bench.json")
    a = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    workers = [int(w) for w in a.workers.split(",")]
    n_chunks = max(workers)  # one round at the widest arm, whole rounds below
    chunk = a.games // n_chunks
    if chunk * n_chunks != a.games:
        sys.exit(f"--games {a.games} must divide by {n_chunks} "
                 f"(the widest worker count) for whole rounds in every arm")
    print(f"[genbench] {a.games} games, chunk {chunk} -> {n_chunks} chunks; "
          f"arms {workers}")

    server = _start_server(CKPT, a.port, RUNS_DIR / "genbench-server.log",
                           sample=True, mu_out=RUNS_DIR / "genbench-mu.jsonl",
                           temperature=1.0)
    results = []
    try:
        for w in workers:
            print(f"[genbench] workers={w} ...")
            r = arm(w, a.games, chunk, a.games_per_pair, a.port, a.seed_base)
            print(f"           {r}")
            results.append(r)
    finally:
        _stop_server(server)

    Path(ROOT / a.out).write_text(json.dumps(
        {"games": a.games, "chunk": chunk, "ckpt": CKPT,
         "results": results}, indent=2))
    print(f"[genbench] wrote {a.out}")
    ok = [r for r in results if r.get("ok")]
    if ok:
        print("\n  workers   games/h   decisive")
        for r in ok:
            print(f"  {r['workers']:>7}   {r['games_per_hour']:>7}   "
                  f"{r['decisive']}/{r['games']}")
        best = max(ok, key=lambda r: r["games_per_hour"])
        notify("anvil genbench complete",
               f"best {best['workers']}w = {best['games_per_hour']} g/h",
               tag="genbench")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        # argparse --help and clean sys.exit(0) raise SystemExit too; only a
        # NONZERO code is a failure. The first version caught BaseException
        # flat and pushed "read FAILED SystemExit: 0" from a --help call.
        if e.code not in (0, None):
            notify("anvil genbench FAILED", f"exit {e.code}", tag="genbench")
        raise
    except BaseException as e:  # noqa: BLE001 — a job that dies must SAY so
        notify("anvil genbench FAILED", f"{type(e).__name__}: {e}", tag="genbench")
        raise
