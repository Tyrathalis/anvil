"""M6 D2-A labeling re-price (m6-plan D2-A.1, seeded by ADR-0039's
"between" verdict): re-bench the parked rollout-label machinery
(ADR-0015) on the modern serve stack.

The stale number being retired: ~17 positions/h/worker at K=8 with
turn-stratified points, measured 2026-07-13 through a BATCH-1 server
(~59 rps) — "50K labels ~= 15 days". Since then the serve path gained
GPU micro-batching (D6) and the w=16 + >=2-round chunk clamp recipe
(ADR-0032, ~+30% in-loop). This bench runs the same labeler mode
(`-rollout K -points M`, uniform distinct fork turns in [2,16] — the
"turn-stratified" configuration) through today's stack and reports
positions/h/worker + campaign arithmetic.

Serve: argmax on the ckpt of record (matches the ADR-0015 measurement
basis; a sampled campaign differs only by mu bookkeeping). Census OFF in
labeler runs (standing rule, ADR-0015; the fork warns otherwise).
Chunk: auto >=2 rounds per worker (the chunk-tail lesson). This is a
pricing bench, not a calibrated read — desktop noise is acceptable.

Usage:
  uv run python scripts/bench_labeler.py --smoke          # plumbing check
  uv run python scripts/bench_labeler.py                  # the re-price
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
                                     _stop_server, batch_chunk)

CKPT = "data/training/d6-run11/iter-019/train/last.pt"
ADR_0015 = {"pos_per_h_per_worker": 17.0, "server_rps": 59,
            "note": "batch-1 server, turn-stratified points, K=8 (2026-07-13)"}


def run_arm(a, purpose: str, games: int, workers: int, points: int,
            k: int) -> dict:
    before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
    chunk = batch_chunk(games, workers, a.chunk)
    cmd = [sys.executable, "-m", "anvil.bridge.harness", "launch", "--pool",
           "--games", str(games), "--games-per-pair", str(a.games_per_pair),
           "--workers", str(workers), "--chunk", str(chunk),
           "--bridge", f"grpc:localhost:{a.port}",
           "--obs", "--reask",
           "--rollout-k", str(k), "--rollout-points", str(points),
           "--purpose", purpose, "--seed-base", str(a.seed_base)]
    t0 = time.monotonic()
    p = subprocess.run(cmd, cwd=ROOT)
    elapsed = time.monotonic() - t0
    if p.returncode != 0:
        return {"ok": False, "elapsed_s": round(elapsed, 1)}

    new = set(glob.glob(str(RUNS_DIR / f"{purpose}-*"))) - before
    rd = Path(new.pop()) if len(new) == 1 else None
    # dedupe by (game, fork point): crash re-launches replay partial games
    # and re-append their label rows (85/689 in the first bench)
    uniq: dict[tuple, dict] = {}
    if rd is not None:
        for lf in sorted(rd.glob("workers/inv-*/labels.jsonl")):
            for line in lf.read_text().splitlines():
                try:
                    r = json.loads(line)
                    uniq[(r["i"], r["fp"])] = r
                except (json.JSONDecodeError, KeyError):
                    continue
    rows = list(uniq.values())
    decisive = 0
    if rd is not None and (rd / "games.jsonl").exists():
        decisive = sum(1 for line in open(rd / "games.jsonl")
                       if json.loads(line).get("status") == "won")
    n_ok = sum(1 for r in rows if sum(r["w"]) + r["draw"] > 0)
    ms = sorted(r["ms"] for r in rows)
    copy_ms = sorted(r["copy_ms"] for r in rows)
    h = elapsed / 3600
    res = {
        "ok": True, "run_dir": str(rd), "elapsed_s": round(elapsed, 1),
        "games": games, "workers": workers, "chunk": chunk,
        "rollout_k": k, "points": points,
        "decisive_mainlines": decisive,
        "labels": len(rows), "labels_scored": n_ok,
        "completion_crashes": sum(r["crash"] for r in rows),
        "draws": sum(r["draw"] for r in rows),
        "pos_per_h": round(len(rows) / h, 1),
        "pos_per_h_per_worker": round(len(rows) / h / workers, 2),
        "mainline_games_per_h": round(games / h, 1),
        "fork_block_ms": {"p50": ms[len(ms) // 2] if ms else None,
                          "p90": ms[int(len(ms) * .9)] if ms else None,
                          "max": ms[-1] if ms else None},
        "copy_ms_p50": copy_ms[len(copy_ms) // 2] if copy_ms else None,
    }
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=160)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--rollout-k", type=int, default=8)
    ap.add_argument("--points", type=int, default=4)
    ap.add_argument("--games-per-pair", type=int, default=5)
    ap.add_argument("--chunk", type=int, default=30, help="ceiling; auto-clamped")
    ap.add_argument("--port", type=int, default=50069)
    ap.add_argument("--ckpt", default=CKPT)
    ap.add_argument("--seed-base", type=int, default=20260805)
    ap.add_argument("--out", default="data/runs/labeler-bench.json")
    ap.add_argument("--smoke", action="store_true",
                    help="tiny plumbing run (8 games, w=8, K=4, 2 points); "
                         "timing not meaningful")
    a = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    if a.smoke:
        games, workers, points, k, purpose = 8, 8, 2, 4, "labelsmoke"
    else:
        games, workers, points, k = a.games, a.workers, a.points, a.rollout_k
        purpose = f"labelbench-w{workers}"

    log = Path(a.out).with_suffix(".server.log")
    print(f"[bench] server: argmax {a.ckpt} :{a.port}")
    server = _start_server(a.ckpt, a.port, log, sample=False)
    try:
        res = run_arm(a, purpose, games, workers, points, k)
    finally:
        _stop_server(server)

    res["ckpt"] = a.ckpt
    res["adr0015_basis"] = ADR_0015
    if res.get("ok") and not a.smoke:
        speedup = res["pos_per_h_per_worker"] / ADR_0015["pos_per_h_per_worker"]
        res["speedup_vs_adr0015"] = round(speedup, 2)
        res["campaign_arithmetic"] = {
            "labels_50k_days": round(50_000 / res["pos_per_h"] / 24, 1),
            "labels_10k_hours": round(10_000 / res["pos_per_h"], 1),
            "labels_5k_hours": round(5_000 / res["pos_per_h"], 1),
        }
    Path(a.out).write_text(json.dumps(res, indent=2) + "\n")
    print(json.dumps(res, indent=2))
    if not a.smoke:
        notify("labeler re-price bench done",
               f"{res.get('pos_per_h_per_worker')} pos/h/worker "
               f"(ADR-0015: 17) -> {a.out}")


if __name__ == "__main__":
    main()
