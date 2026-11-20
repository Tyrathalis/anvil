"""The head-to-head read: checkpoint A against checkpoint B, network-alone.

Both seats are bridged and one argmax server answers them, routed by seat
(`anvil.bridge.server --seat-ckpt`). Each seat assignment runs the same
seeded games as the standard read (`final_read.py`): in arm s0 A sits at
seat 0 and B at seat 1, in arm s1 they swap. The report is A's score over
both arms, with the standard error taken over game indices so that the two
seatings of one seeded game count as one sample.

A draw scores one half for each side. A crashed game scores for neither and
is reported. The driver refuses a result whose server did not see asks from
both seats, or could not read the seat of any ask.

Why it exists: every other read measures strength against the heuristic
alone; this one puts two checkpoints at the same table.

Usage:
  uv run python scripts/h2h_read.py \
      --a data/training/big-run/iter-405/train/last.pt \
      --b data/training/shakedown-alloc/iter-019/train/last.pt \
      --name h2h-405-start --games 1000 --seed-base 20261115 --jar <snapshot jar>
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import sys
from pathlib import Path

from anvil.training.selfplay import (
    RUNS_DIR,
    _new_run_dir,
    _run,
    _start_server,
    _stop_server,
    fleet_bridge,
    fleet_size,
    launch_queue,
)


def game_score(g: dict, a_seat: int) -> float | None:
    """A's score in one game record: 1 win, 0 loss, 0.5 draw; None = the
    game crashed and scores for neither. With every seat bridged the winner
    string names the seat as `(n)`, one-based."""
    status = g.get("status", "")
    if status.startswith("crash"):
        return None
    if status != "won":
        return 0.5
    winner = g.get("winner") or ""
    if f"({a_seat + 1})" in winner:
        return 1.0
    if f"({2 - a_seat})" in winner:
        return 0.0
    raise ValueError(f"game {g.get('i')}: winner {winner!r} names neither seat")


def score(arms: dict[int, list[dict]]) -> dict:
    """The report from {A's seat: game records}."""
    by_index: dict[int, list[float]] = {}
    per_seat: dict[int, dict] = {}
    tally = {"a_wins": 0, "b_wins": 0, "draws": 0, "crashes": 0}
    seat0_wins = decisive = 0
    for a_seat, games in sorted(arms.items()):
        got: list[float] = []
        for g in games:
            sc = game_score(g, a_seat)
            if sc is None:
                tally["crashes"] += 1
                continue
            tally["a_wins" if sc == 1.0 else "b_wins" if sc == 0.0 else "draws"] += 1
            if sc != 0.5:
                decisive += 1
                seat0_wins += int((sc == 1.0) == (a_seat == 0))
            got.append(sc)
            by_index.setdefault(g["i"], []).append(sc)
        per_seat[a_seat] = {"games": len(got), "a_score": sum(got) / max(len(got), 1)}
    means = [sum(v) / len(v) for v in by_index.values()]
    n = len(means)
    mean = sum(means) / max(n, 1)
    var = sum((m - mean) ** 2 for m in means) / max(n - 1, 1)
    se = math.sqrt(var / max(n, 1))
    return {
        **tally,
        "games_scored": sum(len(v) for v in by_index.values()),
        "indices": n,
        "a_score": mean,
        "se": se,
        "t_vs_half": (mean - 0.5) / se if se > 0 else 0.0,
        "a_score_by_a_seat": per_seat,
        "seat0_winrate_decisive": seat0_wins / max(decisive, 1),
    }


def check_routing(counts: dict, seat_b: int) -> None:
    """Refuse an arm whose server did not route both seats."""
    seen = {int(k): v for k, v in (counts.get("seat_requests") or {}).items()}
    if counts.get("seat_unrouted", 0):
        raise RuntimeError(f"{counts['seat_unrouted']} asks had no readable seat; the arm is not a head-to-head")
    if not seen.get(0) or not seen.get(1):
        raise RuntimeError(f"the server saw asks from seats {sorted(seen)} only; both seats must be bridged")
    if set(seen) - {0, 1}:
        raise RuntimeError(f"asks from unexpected seats {sorted(seen)}")
    if not any(k.startswith(f"seat{seat_b}_") for k in counts):
        raise RuntimeError(f"no counters from the seat-{seat_b} checkpoint: it answered nothing")


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description="head-to-head read of two checkpoints, network-alone")
    ap.add_argument("--a", required=True, help="checkpoint A (the score is A's)")
    ap.add_argument("--b", required=True, help="checkpoint B")
    ap.add_argument("--name", required=True, help="report prefix, e.g. h2h-405-start")
    ap.add_argument("--games", type=int, default=1000, help="games per seat assignment")
    ap.add_argument("--games-per-pair", type=int, default=5)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--chunk", type=int, default=None, help="default ceil(games / (4 * workers))")
    ap.add_argument("--port", type=int, default=50086)
    ap.add_argument("--servers", type=int, default=0, help="0 = ceil(workers / 12)")
    ap.add_argument("--pairs-file", default="data/runs/d5arm-d0-s0-20260714-143546/pairs.txt")
    ap.add_argument("--seed-base", type=int, required=True)
    ap.add_argument("--pool-version", default=None)
    ap.add_argument("--format", default="Commander")
    ap.add_argument("--jar", default=None, help="run this jar (a snapshot copy) instead of target/'s newest")
    ap.add_argument("--server-args", default=None, help="extra model-server flags for both checkpoints")
    ap.add_argument(
        "--cells", action="store_true",
        help="one seat arm at a time, each under its own server fleet on --port (the pre-Build-2 read). "
        "Default: both arms through one queue, each arm's fleet on its own ports (--port and the block "
        "after it), so twice the servers are up at once",
    )
    a = ap.parse_args()
    if a.chunk is None:
        a.chunk = max(1, -(-a.games // (4 * a.workers)))
    if a.pool_version is None:
        from anvil.bridge.harness.pairs import latest_pool_manifest

        a.pool_version = latest_pool_manifest("dc")["pool_version"]

    arms: dict[int, list[dict]] = {}
    arm_dirs: dict[int, str] = {}
    n_srv = fleet_size(a)

    def _arm(a_seat: int, port: int):
        """(purpose, counts file, server start thunk, launch flags) for the arm with A at `a_seat`."""
        b_seat = 1 - a_seat
        counts = RUNS_DIR / f"{a.name}-s{a_seat}-server.counts.json"
        counts.unlink(missing_ok=True)
        purpose = f"{a.name}arm-s{a_seat}"

        def start():
            return _start_server(
                a.a, port, RUNS_DIR / f"{a.name}-s{a_seat}-server.log", sample=False,
                sched_flags=["--seat-ckpt", f"{b_seat}={a.b}", "--counts-out", str(counts)]
                + (a.server_args.split() if a.server_args else []),
                servers=n_srv,
            )

        argv = [
            "--pairs-file", a.pairs_file, "--format", a.format,
            "--games", str(a.games), "--games-per-pair", str(a.games_per_pair),
            "--workers", str(a.workers), "--chunk", str(a.chunk),
            "--bridge", fleet_bridge(a, port=port), "--census", "--obs",
            "--purpose", purpose, "--seed-base", str(a.seed_base),
            "--pool-version", a.pool_version, "--reask",
            *(["--jar", a.jar] if a.jar else []),
        ]
        return purpose, counts, start, argv

    got: dict[int, Path] = {}
    all_counts: dict[int, Path] = {}
    if a.cells:
        for a_seat in (0, 1):
            purpose, counts, start, argv = _arm(a_seat, a.port)
            all_counts[a_seat] = counts
            before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
            server = start()
            try:
                _run([sys.executable, "-m", "anvil.bridge.harness", "launch", *argv])
            finally:
                _stop_server(server)
            got[a_seat] = _new_run_dir(purpose, before)
    else:
        # one queue across the seat arms (M13 Build 2). The seat routing is the
        # server's, so each arm keeps its own fleet, on its own block of ports.
        plan = [_arm(a_seat, a.port + a_seat * n_srv) for a_seat in (0, 1)]
        servers = []
        try:
            for _, _, start, _ in plan:
                servers.append(start())
            dirs = launch_queue(f"{a.name}-q", a.workers, [(p, argv, None) for p, _, _, argv in plan])
        finally:
            for srv in servers:
                _stop_server(srv)
        for a_seat, rd in zip((0, 1), dirs):
            got[a_seat] = rd
            all_counts[a_seat] = plan[a_seat][1]

    for a_seat in (0, 1):
        b_seat = 1 - a_seat
        rd = got[a_seat]
        manifest = json.loads((rd / "run.json").read_text())
        if manifest.get("bridge_seats") is not None:
            raise RuntimeError(f"{rd.name}: bridge_seats={manifest['bridge_seats']}; every seat must be bridged")
        check_routing(json.loads(all_counts[a_seat].read_text()), b_seat)
        # which checkpoint sat where: the run manifest cannot say
        (rd / "h2h-seats.json").write_text(json.dumps({str(a_seat): a.a, str(b_seat): a.b}, indent=1) + "\n")
        arms[a_seat] = [json.loads(line) for line in (rd / "games.jsonl").read_text().splitlines()]
        arm_dirs[a_seat] = str(rd)
        print(f"[h2h] arm s{a_seat} done: {rd.name}")

    rep = {"a": a.a, "b": a.b, "seed_base": a.seed_base, "games_per_seat": a.games, "arm_dirs": arm_dirs, **score(arms)}
    out = RUNS_DIR / f"{a.name}-h2h.json"
    out.write_text(json.dumps(rep, indent=1) + "\n")
    print(
        f"[h2h] A score {rep['a_score']:.4f} ± {rep['se']:.4f} (t {rep['t_vs_half']:+.2f} vs 0.5; "
        f"{rep['a_wins']} A wins / {rep['b_wins']} B wins / {rep['draws']} draws / {rep['crashes']} crashes; "
        f"seat-0 winrate {rep['seat0_winrate_decisive']:.3f})"
    )
    print(f"[h2h] report: {out}")


if __name__ == "__main__":
    main()
