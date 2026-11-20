"""Price the search in generation: the same self-play cell with the search on and off (M13 pre-scoping, §3; a utility).

Plays one generation cell of the recipe of record twice from one checkpoint, on the same seeds and
the same fleet, sampled serving as the loop does it: once with the loop's search flags and once
with none. Nothing is trained. It reports, per cell, the wall time, games per hour, and the
worker-seconds and windows per game from the games' own records. Worker-seconds per game does not
depend on how the cell's tail drains; games per hour does. Design and result:
docs/design/m13-prescoping-measurements.md, §3.

    uv run python scripts/search_wall_cost.py --out data/runs/search-wall-cost
"""
import argparse
import glob
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from anvil.training.selfplay import RUNS_DIR, _start_server, _stop_server, sched_flags  # noqa: E402

SEARCH = ("-search -searchrate 1 -searchrolls 2 -searchsurf 2 -searchsurfcap 8 -searchact 0.10 -searchtemp 0.025 "
          "-searchactkinds entity_one,entity_set,mode -searchalloc {tau} -searchfloor 0.1")


def cell(a, name: str, forge_args: str, loop_cfg: argparse.Namespace) -> dict:
    out = Path(a.out)
    done = out / f"{name}.json"
    if done.exists():
        return json.load(open(done))
    purpose = f"swc-{name}"
    before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
    mu = out / f"{name}.mu.jsonl"
    if mu.exists():
        mu.unlink()
    server = _start_server(a.ckpt, a.port, out / f"{name}.server.log", sample=True, mu_out=mu, temperature=1.0,
                           sched_flags=sched_flags(loop_cfg), servers=a.servers)
    cmd = [sys.executable, "-m", "anvil.bridge.harness", "launch", "--pool", "--pool-format", "dc", "--format",
           "Commander", "--games", str(a.games), "--games-per-pair", "2", "--start-index", str(a.start_index),
           "--workers", str(a.workers), "--chunk", str(a.chunk), "--bridge",
           ",".join(f"grpc:localhost:{a.port + i}" for i in range(a.servers)), "--obs", "--census",
           "--purpose", purpose, "--seed-base", str(a.seed_base), "--reask", "--jar", a.jar]
    if forge_args:
        cmd += [f"--forge-args={forge_args}", "--labels"]
    print("[swc] $", " ".join(cmd), flush=True)
    t0 = time.monotonic()
    try:
        rc = subprocess.run(cmd, cwd=ROOT).returncode
    finally:
        elapsed = time.monotonic() - t0
        _stop_server(server)
    new = set(glob.glob(str(RUNS_DIR / f"{purpose}-*"))) - before
    rd = new.pop() if len(new) == 1 else None
    games = [json.loads(ln) for f in glob.glob(f"{rd}/workers/*/games.jsonl") for ln in open(f)] if rd else []
    ms = sum(g.get("ms") or 0 for g in games)
    n = max(1, len(games))
    rec = {"cell": name, "rc": rc, "run_dir": rd, "forge_args": forge_args, "elapsed_s": round(elapsed, 1),
           "games": len(games), "games_per_hour": round(len(games) / elapsed * 3600, 1),
           "worker_s_per_game": round(ms / 1000 / n, 1), "windows_per_game": round(sum(g.get("windows") or 0 for g in games) / n, 1),
           "turns_per_game": round(sum(g.get("turns") or 0 for g in games) / n, 1),
           "statuses": {s: sum(g.get("status") == s for g in games) for s in sorted({str(g.get("status")) for g in games})},
           "draw_clock": sum(bool(g.get("draw_clock")) for g in games),
           "longest_game_s": round(max((g.get("ms") or 0 for g in games), default=0) / 1000, 1),
           "mu_rows": sum(1 for _ in open(mu)) if mu.exists() else None}
    if rc == 0:
        json.dump(rec, open(done, "w"), indent=1)
    print("[swc]", json.dumps(rec), flush=True)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ckpt", default="data/training/big-run/iter-405/train/last.pt")
    ap.add_argument("--loop-config", default="data/training/big-run/loop_config.json",
                    help="the run whose serving flags (the schedule's) the cells copy")
    ap.add_argument("--tau", default="0.01855", help="the checkpoint's allocation threshold (its config's alloc fit)")
    ap.add_argument("--games", type=int, default=240)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--servers", type=int, default=2)
    ap.add_argument("--chunk", type=int, default=2)
    ap.add_argument("--port", type=int, default=50080)
    ap.add_argument("--seed-base", type=int, default=20261120)
    ap.add_argument("--start-index", type=int, default=0)
    ap.add_argument("--jar", default=str(ROOT / "data/runs/tgtmask/forge-tgtmask3.jar"))
    ap.add_argument("--cells", default="on,off")
    ap.add_argument("--out", required=True)
    ap.add_argument("--server-args", default=None,
                    help="extra model-server flags (the loop's --server-args), e.g. the merged engine's --abilities")
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    loop_cfg = argparse.Namespace(**json.load(open(a.loop_config)))
    if a.server_args:
        loop_cfg.server_args = a.server_args
    args = {"on": SEARCH.format(tau=a.tau), "off": ""}
    recs = [cell(a, c, args[c], loop_cfg) for c in a.cells.split(",")]
    if all(r["rc"] == 0 for r in recs) and len(recs) == 2:
        on, off = recs
        print("[swc] search on / off: wall per game %.2fx, worker-seconds per game %.2fx" % (
            off["games_per_hour"] / on["games_per_hour"], on["worker_s_per_game"] / off["worker_s_per_game"]))
    json.dump(recs, open(Path(a.out) / "report.json", "w"), indent=1)
    sys.exit(max(r["rc"] for r in recs))


if __name__ == "__main__":
    main()
