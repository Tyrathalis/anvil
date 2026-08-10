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

CHUNK-TAIL HAZARD (learned 2026-08-03 the expensive way): if an arm gets
fewer than 2 chunks per worker there is no refill — elapsed time equals the
SLOWEST worker's chunk, and chunks are contiguous deck-pair blocks with
heavily correlated game lengths. A single-arm `--workers 8` invocation used
to size chunk = games/8 (exactly one round), which measured ~37% slow with
an 11x worker-finish tail and masqueraded as an environment regression
(seven exonerated suspects, one kernel swap, two package downgrades). Every
arm now gets >=2 rounds by construction; the divisibility error tells you a
valid --games. Cross-era throughput comparisons are only valid at IDENTICAL
chunking.

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

from anvil.training.notify import notify
from anvil.training.selfplay import RUNS_DIR, _start_server, _stop_server

CKPT = "data/training/d6-run7b/iter-014/train/last.pt"


def arm(
    workers: int,
    games: int,
    chunk: int,
    gpp: int,
    port: int,
    seed_base: int,
    calibrated: bool = False,
) -> dict:
    purpose = f"genbench-w{workers}"
    before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
    cmd = [
        sys.executable,
        "-m",
        "anvil.bridge.harness",
        "launch",
        "--pool",
        "--games",
        str(games),
        "--games-per-pair",
        str(gpp),
        "--workers",
        str(workers),
        "--chunk",
        str(chunk),
        "--bridge",
        f"grpc:localhost:{port}",
        "--obs",
        "--census",
        "--reask",
        "--purpose",
        purpose,
        "--seed-base",
        str(seed_base),
    ]
    if calibrated:
        cmd.append("--calibrated")
    t0 = time.monotonic()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    elapsed = time.monotonic() - t0
    if p.returncode != 0:
        return {"workers": workers, "ok": False, "error": (p.stderr or p.stdout)[-1200:]}

    new = set(glob.glob(str(RUNS_DIR / f"{purpose}-*"))) - before
    rd = Path(new.pop()) if len(new) == 1 else None
    decisive = crashed = 0
    if rd is not None and (rd / "games.jsonl").exists():
        with open(rd / "games.jsonl") as f:
            for line in f:
                r = json.loads(line)
                if r.get("status") == "won":
                    decisive += 1
                else:
                    crashed += 1
    return {
        "workers": workers,
        "ok": True,
        "elapsed_s": round(elapsed, 1),
        "games": games,
        "games_per_hour": round(games / elapsed * 3600, 1),
        "decisive": decisive,
        "nondecisive": crashed,
        "run_dir": str(rd) if rd else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=240)
    ap.add_argument("--workers", default="8,16")
    ap.add_argument("--games-per-pair", type=int, default=5)
    ap.add_argument("--port", type=int, default=50068)
    ap.add_argument("--seed-base", type=int, default=20260726)
    ap.add_argument("--out", default="data/runs/generation-bench.json")
    ap.add_argument(
        "--chunk",
        type=int,
        default=0,
        help="explicit chunk size (0 = auto: >=2 rounds per arm); "
        "refuses tail-bound configs (<2 rounds at the widest "
        "arm)",
    )
    ap.add_argument(
        "--calibrated",
        action="store_true",
        help="pass --calibrated to the harness: workers NOT "
        "reniced (nice differential measured ~1%% — the "
        "2026-08-03 '37%% slow' was the chunk-tail artifact, "
        "not nice)",
    )
    a = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    workers = [int(w) for w in a.workers.split(",")]
    if a.chunk:
        chunk = a.chunk
        n_chunks = a.games // chunk
    else:
        # >=2 rounds for EVERY arm including the widest — a no-refill arm
        # measures its slowest contiguous pair-block, not throughput
        n_chunks = 2 * max(workers)
        chunk = a.games // n_chunks
    if chunk == 0 or chunk * n_chunks != a.games:
        lo = (a.games // n_chunks) * n_chunks
        good = ", ".join(str(g) for g in (lo, lo + n_chunks) if g)
        sys.exit(
            f"--games {a.games} must divide into whole chunks "
            f"({n_chunks} needed); nearby valid --games: {good}"
        )
    if n_chunks < 2 * max(workers):
        sys.exit(
            f"chunk {chunk} gives {n_chunks} chunks for {max(workers)} "
            f"workers (<2 rounds) — the tail-bound regime measures the "
            f"slowest worker, not throughput. Use a smaller --chunk."
        )
    print(
        f"[genbench] {a.games} games, chunk {chunk} -> {n_chunks} chunks "
        f"({n_chunks / max(workers):.0f} rounds at widest); arms {workers}"
    )

    server = _start_server(
        CKPT,
        a.port,
        RUNS_DIR / "genbench-server.log",
        sample=True,
        mu_out=RUNS_DIR / "genbench-mu.jsonl",
        temperature=1.0,
    )
    results = []
    try:
        for w in workers:
            print(f"[genbench] workers={w} ...")
            r = arm(
                w, a.games, chunk, a.games_per_pair, a.port, a.seed_base, calibrated=a.calibrated
            )
            print(f"           {r}")
            results.append(r)
    finally:
        _stop_server(server)

    Path(ROOT / a.out).write_text(
        json.dumps({"games": a.games, "chunk": chunk, "ckpt": CKPT, "results": results}, indent=2)
    )
    print(f"[genbench] wrote {a.out}")
    ok = [r for r in results if r.get("ok")]
    if ok:
        print("\n  workers   games/h   decisive")
        for r in ok:
            print(f"  {r['workers']:>7}   {r['games_per_hour']:>7}   {r['decisive']}/{r['games']}")
        best = max(ok, key=lambda r: r["games_per_hour"])
        notify(
            "anvil genbench complete",
            f"best {best['workers']}w = {best['games_per_hour']} g/h",
            tag="genbench",
        )


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
    except BaseException as e:
        notify("anvil genbench FAILED", f"{type(e).__name__}: {e}", tag="genbench")
        raise
