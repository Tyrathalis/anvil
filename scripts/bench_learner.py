"""RL-learner throughput benchmark: where does the train phase's wall clock go?

The train phase is 62% of a run's wall clock (run-7b: 16.6h of 26.8h) and the
critic phase inside it is ~2 min — so the V-trace learner IS the run. It moves
~550 window-forwards/s against BC training's ~3,640 windows/s on the same model,
and the question this script answers is WHY: GPU-bound (segments too small to
fill the device) or loader-bound (CPU featurization starving it).

The two hypotheses separate cleanly:
  - GPU-bound  -> throughput rises with --seg, flat in --workers
  - loader-bound -> throughput rises with --workers, flat in --seg

Replays a real run-8 iteration invocation verbatim except for --max-traj (cap),
--seg, and --workers, so the measured shape is the production one. Samples GPU
utilization through each arm — a low busy fraction is the loader-bound tell
regardless of which knob moves the number.

Run it on a QUIET box (no generation workers, no ComfyUI): the whole point is
that the seg autotune has been picking 128 because a resident ComfyUI leaves
~13GB free, and we want to know what a clear GPU buys.

Usage: uv run python scripts/bench_learner.py [--traj 40] [--out <json>]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv/bin/python"

# run-8 iter-005 verbatim (driver.log), minus the knobs under test.
ITER = "d6-run8"
STORES = [
    "d6-run8-i002-20260723-212414",
    "d6-run8-i002h0-20260723-214323",
    "d6-run8-i002h1-20260723-215954",
    "d6-run8-i003-20260723-234052",
    "d6-run8-i003h0-20260724-000107",
    "d6-run8-i003h1-20260724-001322",
    "d6-run8-i004-20260724-021307",
    "d6-run8-i004h0-20260724-023006",
    "d6-run8-i004h1-20260724-024035",
    "d6-run8-i005-20260724-051443",
    "d6-run8-i005h0-20260724-053218",
    "d6-run8-i005h1-20260724-054115",
]
WEIGHTS = [0.33] * 9 + [1.0] * 3
CKPT = f"data/training/{ITER}/iter-004/train/last.pt"
CRITIC = f"data/training/{ITER}/iter-005/critic/last.pt"


class GpuSampler(threading.Thread):
    """Poll utilization/memory at 2 Hz for the life of one arm."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.stop = threading.Event()
        self.util: list[float] = []
        self.mem: list[float] = []

    def run(self) -> None:
        while not self.stop.is_set():
            try:
                out = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=utilization.gpu,memory.used",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                ).stdout.strip()
                u, m = out.split(",")
                self.util.append(float(u))
                self.mem.append(float(m))
            except Exception:
                pass
            self.stop.wait(0.5)


def arm(seg: int, workers: int, traj: int, scratch: Path) -> dict:
    out = scratch / f"seg{seg}-w{workers}"
    if out.exists():
        shutil.rmtree(out)
    cmd = [
        str(PY),
        "-m",
        "anvil.training.rl",
        "--store",
        ",".join(f"data/trajectories/{s}" for s in STORES),
        "--weights",
        ",".join(str(w) for w in WEIGHTS),
        "--ckpt",
        CKPT,
        "--critic-ckpt",
        CRITIC,
        "--out",
        str(out),
        "--lr",
        "1e-05",
        "--ent-weight",
        "0.003",
        "--ent-floor",
        "0.08",
        "--value-weight",
        "0.5",
        "--traj-per-step",
        "8",
        "--penalty",
        "0.02",
        "--epochs",
        "1",
        "--seed",
        "5",
        "--seg",
        str(seg),
        "--workers",
        str(workers),
        "--max-traj",
        str(traj),
    ]
    sampler = GpuSampler()
    sampler.start()
    t0 = time.monotonic()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    elapsed = time.monotonic() - t0
    sampler.stop.set()
    sampler.join(timeout=3)

    if p.returncode != 0:
        tail = (p.stderr or p.stdout)[-1500:]
        return {"seg": seg, "workers": workers, "ok": False, "error": tail}

    # windows/s: the learner prints "done: N steps, M trajectories"; window
    # counts come from win_per_s in the last metrics row (its own t0 includes
    # model load, so recompute from the row's absolute counts where possible).
    n_traj = None
    m = re.search(r"done: \d+ steps, (\d+) trajectories", p.stdout)
    if m:
        n_traj = int(m.group(1))
    wps = None
    for line in reversed(p.stdout.splitlines()):
        mm = re.search(r"'win_per_s': ([\d.]+)", line)
        if mm:
            wps = float(mm.group(1))
            break

    return {
        "seg": seg,
        "workers": workers,
        "ok": True,
        "elapsed_s": round(elapsed, 1),
        "trajectories": n_traj,
        "traj_per_s": round(n_traj / elapsed, 3) if n_traj else None,
        "learner_win_per_s": wps,
        "gpu_util_mean": round(statistics.mean(sampler.util), 1) if sampler.util else None,
        "gpu_util_p90": round(sorted(sampler.util)[int(len(sampler.util) * 0.9)], 1)
        if len(sampler.util) > 10
        else None,
        "gpu_busy_frac": round(sum(u > 25 for u in sampler.util) / len(sampler.util), 3)
        if sampler.util
        else None,
        "gpu_mem_peak_mb": round(max(sampler.mem)) if sampler.mem else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--traj", type=int, default=40, help="trajectories per arm (wall clock scales with this)"
    )
    ap.add_argument("--out", default="data/runs/learner-bench.json")
    ap.add_argument("--segs", default="64,128,256,512")
    ap.add_argument(
        "--workers", default="6,12", help="loader worker counts; the seg sweep runs at the first"
    )
    args = ap.parse_args()

    segs = [int(s) for s in args.segs.split(",")]
    workers = [int(w) for w in args.workers.split(",")]
    scratch = ROOT / "data/runs/_bench_scratch"
    scratch.mkdir(parents=True, exist_ok=True)

    free = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    print(f"[bench] GPU at start: {free}")
    print(
        f"[bench] {len(segs)} seg arms + {len(workers) - 1} worker arms, "
        f"{args.traj} trajectories each\n"
    )

    results = []
    # seg sweep at the baseline worker count
    for seg in segs:
        print(f"[bench] seg={seg} workers={workers[0]} ...", flush=True)
        r = arm(seg, workers[0], args.traj, scratch)
        print(f"        {r}\n", flush=True)
        results.append(r)

    # worker sweep at the best seg so far — separates loader-bound from GPU-bound
    ok = [r for r in results if r.get("ok") and r.get("traj_per_s")]
    best_seg = max(ok, key=lambda r: r["traj_per_s"])["seg"] if ok else segs[-1]
    for w in workers[1:]:
        print(f"[bench] seg={best_seg} workers={w} ...", flush=True)
        r = arm(best_seg, w, args.traj, scratch)
        print(f"        {r}\n", flush=True)
        results.append(r)

    rec = {
        "traj_per_arm": args.traj,
        "source_iteration": f"{ITER}/iter-005 invocation",
        "gpu_at_start": free,
        "results": results,
    }
    Path(ROOT / args.out).write_text(json.dumps(rec, indent=2))
    print(f"[bench] wrote {args.out}")

    if ok:
        print("\n  seg  workers  traj/s   gpu_busy  gpu_mem_mb")
        for r in results:
            if r.get("ok"):
                print(
                    f"  {r['seg']:>4} {r['workers']:>7}  {r['traj_per_s']:>6} "
                    f"  {r['gpu_busy_frac']:>7}  {r['gpu_mem_peak_mb']:>9}"
                )


if __name__ == "__main__":
    sys.exit(main())
