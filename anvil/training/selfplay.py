"""D6 V-trace self-play loop driver (docs/design/d6-vtrace-loop.md).

Synchronous iterations on one GPU: serve ckpt_k with sampling on -> generate
a batch of both-seats-bridged games -> ingest (mu.jsonl joined) -> V-trace
train on a replay mixture of recent iteration stores -> ckpt_{k+1} -> monitor
row -> restart server on the new checkpoint. Arms vs the heuristic every N
iterations (argmax serve, paired seeds) as the progress meter.

The driver owns sequencing, provenance, and the anomaly monitor — mechanism
stays in the existing verbs (server, harness launch, store ingest, rl
learner, arms_report), each run in its own subprocess so GPU memory is
released between the serve and train phases.

Stop file: touch <out>/STOP to finish the current iteration and exit; resume
by re-running the same command (loop_state.json carries the chain).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

RUNS_DIR = Path("data/runs")
TRAJ_DIR = Path("data/trajectories")


def _wait_port(port: int, timeout: float = 300.0) -> None:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(1)
    raise TimeoutError(f"server never opened port {port}")


def _start_server(ckpt: str, port: int, log: Path, sample: bool,
                  mu_out: Path | None = None, temperature: float = 1.0):
    cmd = [sys.executable, "-m", "anvil.bridge.server", "--mode", "model",
           "--ckpt", ckpt, "--port", str(port), "--pass-delta", "0"]
    if sample:
        cmd += ["--sample", "--temperature", str(temperature),
                "--mu-out", str(mu_out)]
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(cmd, stdout=open(log, "w"), stderr=subprocess.STDOUT,
                            env=env)
    try:
        _wait_port(port)
    except TimeoutError:
        proc.kill()
        raise
    return proc


def _stop_server(proc) -> None:
    proc.send_signal(signal.SIGINT)  # prints its stats on the way out
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


def _run(cmd: list[str]) -> None:
    print(f"[selfplay] $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def _launch_games(purpose: str, games: int, start_index: int, a) -> Path:
    before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
    _run([sys.executable, "-m", "anvil.bridge.harness", "launch", "--pool",
          "--games", str(games), "--games-per-pair", str(a.games_per_pair),
          "--start-index", str(start_index), "--workers", str(a.workers),
          "--chunk", str(a.chunk), "--bridge", f"grpc:localhost:{a.port}",
          "--obs", "--census", "--purpose", purpose,
          "--seed-base", str(a.seed_base)])
    new = set(glob.glob(str(RUNS_DIR / f"{purpose}-*"))) - before
    if len(new) != 1:
        raise RuntimeError(f"expected one new run dir for {purpose}, got {new}")
    return Path(new.pop())


def _census_tallies(run_dir: Path) -> dict:
    """Field semantics mirror scripts/arms_report.py: priority records carry
    veto (string reason) / pick=="pass" / else cast."""
    from collections import Counter
    c: Counter[str] = Counter()
    for f in run_dir.glob("workers/inv-*/census.jsonl"):
        for line in open(f):
            r = json.loads(line)
            if r.get("by") != "bridge":
                continue
            c["bridged"] += 1
            if r.get("fallback") is True:
                c["fallback"] += 1
            if r.get("m") == "chooseSpellAbilityToPlay":
                if r.get("veto"):
                    c["veto"] += 1
                elif r.get("pick") == "pass":
                    c["pass"] += 1
                else:
                    c["cast"] += 1
            for k in ("dropped", "forced"):
                if r.get(k):
                    c[f"combat_{k}"] += r[k]
    c["veto_rate"] = round(c["veto"] / max(1, c["veto"] + c["cast"]), 4)
    return dict(c)


def _game_stats(run_dir: Path) -> dict:
    import statistics
    rows = []
    for f in run_dir.glob("workers/inv-*/games.jsonl"):
        rows += [json.loads(line) for line in open(f)]
    statuses: dict[str, int] = {}
    for r in rows:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    return {"games": len(rows), "statuses": statuses,
            "turns_median": statistics.median(r["turns"] for r in rows) if rows else None,
            "seat0_wins": sum(1 for r in rows if r.get("status") == "won"
                              and "(1)" in (r.get("winner") or ""))}


def _rl_summary(train_dir: Path) -> dict:
    rows = [json.loads(line) for line in open(train_dir / "metrics.jsonl")]
    if not rows:
        return {}
    last = rows[-1]
    n = max(1, len(rows))
    mean = {k: round(sum(r[k] for r in rows) / n, 5)
            for k in ("reward", "v0", "rho_mean", "rho_clip", "kl_mu", "ent")
            if all(k in r for r in rows)}
    return {"steps": last.get("step"), "traj": last.get("traj"),
            "tripwire_viol": last.get("tripwire_viol"),
            "skips": last.get("skips"), "mean": mean, "final": last}


def main() -> None:
    ap = argparse.ArgumentParser(description="V-trace self-play loop (M2 D6)")
    ap.add_argument("--name", required=True, help="loop name (dirs key off it)")
    ap.add_argument("--ckpt", default="data/training/d5-combat/last.pt",
                    help="iteration-0 init (delta=0 by design)")
    ap.add_argument("--iterations", type=int, required=True)
    ap.add_argument("--games", type=int, default=480, help="games per iteration")
    ap.add_argument("--games-per-pair", type=int, default=2)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--chunk", type=int, default=30)
    ap.add_argument("--port", type=int, default=50063)
    ap.add_argument("--seed-base", type=int, required=True)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--replay", type=int, default=4,
                    help="stores in the training mixture (last R iterations)")
    ap.add_argument("--fresh-weight", type=float, default=1.0,
                    help="expected passes over the newest store per iteration")
    ap.add_argument("--replay-weight", type=float, default=0.33,
                    help="expected passes over each older store (1.0 + 3x0.33 "
                         "≈ two store-scans, 50%% fresh samples)")
    ap.add_argument("--rl-workers", type=int, default=6,
                    help="featurize workers for the learner (its bottleneck)")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--ent-weight", type=float, default=3e-3)
    ap.add_argument("--value-weight", type=float, default=0.5)
    ap.add_argument("--traj-per-step", type=int, default=4)
    ap.add_argument("--arms-every", type=int, default=5,
                    help="arms vs heuristic every N iterations (0 = off)")
    ap.add_argument("--arms-pairs", default=None,
                    help="pairs file for arms runs (D8 valpair schedule)")
    ap.add_argument("--arms-games", type=int, default=200)
    ap.add_argument("--arms-seed-base", type=int, default=20260710)
    args = ap.parse_args()

    out = Path("data/training") / args.name
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "loop_state.json"
    state = (json.loads(state_path.read_text()) if state_path.exists()
             else {"iteration": 0, "ckpt": args.ckpt, "stores": [],
                   "start_index": 0})
    monitor = open(out / "monitor.jsonl", "a", buffering=1)
    (out / "loop_config.json").write_text(json.dumps(vars(args), indent=2))

    while state["iteration"] < args.iterations:
        if (out / "STOP").exists():
            print("[selfplay] STOP file present — exiting between iterations")
            return
        k = state["iteration"]
        it_dir = out / f"iter-{k:03d}"
        it_dir.mkdir(exist_ok=True)
        purpose = f"{args.name}-i{k:03d}"
        print(f"\n[selfplay] ===== iteration {k}: ckpt={state['ckpt']} =====")
        t_iter = time.monotonic()

        # ---- generate (sampled serve) ----
        mu_path = it_dir / "mu.jsonl"
        server = _start_server(state["ckpt"], args.port, it_dir / "server.log",
                               sample=True, mu_out=mu_path,
                               temperature=args.temperature)
        try:
            run_dir = _launch_games(purpose, args.games, state["start_index"], args)
        finally:
            _stop_server(server)
        t_gen = time.monotonic() - t_iter

        # ---- ingest (mu joined on (g, s)) ----
        (run_dir / "mu.jsonl").write_bytes(mu_path.read_bytes())
        _run([sys.executable, "-m", "anvil.store", "ingest", str(run_dir)])
        store = TRAJ_DIR / run_dir.name
        state["stores"].append(str(store))

        # ---- train (V-trace on the replay mixture) ----
        mix = state["stores"][-args.replay:]
        weights = [args.replay_weight] * (len(mix) - 1) + [args.fresh_weight]
        train_dir = it_dir / "train"
        t0 = time.monotonic()
        _run([sys.executable, "-m", "anvil.training.rl",
              "--store", ",".join(mix), "--weights", ",".join(map(str, weights)),
              "--ckpt", state["ckpt"], "--out", str(train_dir),
              "--lr", str(args.lr), "--ent-weight", str(args.ent_weight),
              "--value-weight", str(args.value_weight),
              "--traj-per-step", str(args.traj_per_step),
              "--workers", str(args.rl_workers),
              "--epochs", str(args.epochs), "--seed", str(k)])
        t_train = time.monotonic() - t0
        new_ckpt = train_dir / "last.pt"
        if not new_ckpt.exists():
            raise RuntimeError(f"training produced no checkpoint at {new_ckpt}")

        # ---- monitor row + anomaly flags (accept ckpt AFTER writing it) ----
        census = _census_tallies(run_dir)
        gstats = _game_stats(run_dir)
        rl = _rl_summary(train_dir)
        flags = []
        if census.get("fallback"):
            flags.append(f"fallbacks={census['fallback']}")
        mean = rl.get("mean", {})
        if mean.get("reward") is not None and mean.get("v0") is not None \
                and mean["reward"] - mean["v0"] > 0.1:
            # §6 anomaly rule: winrate exceeding the critic's prediction is a
            # bug report until proven otherwise
            flags.append(f"reward {mean['reward']} >> critic {mean['v0']}")
        if rl.get("tripwire_viol"):
            flags.append(f"tripwire={rl['tripwire_viol']}")
        non_won = {s: n for s, n in gstats["statuses"].items() if s != "won"}
        if sum(non_won.values()) > 0.02 * gstats["games"]:
            flags.append(f"non-decisive {non_won}")
        row = {"iteration": k, "ckpt": state["ckpt"], "run": str(run_dir),
               "store": str(store), "gen_s": round(t_gen), "train_s": round(t_train),
               "census": census, "games": gstats, "rl": rl, "flags": flags}
        monitor.write(json.dumps(row) + "\n")
        if flags:
            print(f"[selfplay] !!! ANOMALY FLAGS iteration {k}: {flags}")

        state.update(iteration=k + 1, ckpt=str(new_ckpt),
                     start_index=state["start_index"] + args.games)
        state_path.write_text(json.dumps(state, indent=2))

        # ---- arms (argmax serve, paired seeds, both seat assignments) ----
        if args.arms_every and (k + 1) % args.arms_every == 0 and args.arms_pairs:
            arm_dirs = []
            server = _start_server(state["ckpt"], args.port,
                                   it_dir / "arms-server.log", sample=False)
            try:
                for seat in (0, 1):
                    ap_purpose = f"{args.name}-arm-i{k:03d}-s{seat}"
                    before = set(glob.glob(str(RUNS_DIR / f"{ap_purpose}-*")))
                    _run([sys.executable, "-m", "anvil.bridge.harness", "launch",
                          "--pairs-file", args.arms_pairs,
                          "--games", str(args.arms_games), "--workers",
                          str(args.workers), "--chunk", "50",
                          "--bridge", f"grpc:localhost:{args.port}",
                          "--census", "--obs", "--purpose", ap_purpose,
                          "--seed-base", str(args.arms_seed_base),
                          "--bridge-seats", str(seat)])
                    new = set(glob.glob(str(RUNS_DIR / f"{ap_purpose}-*"))) - before
                    arm_dirs.append(new.pop())
            finally:
                _stop_server(server)
            _run([sys.executable, "scripts/arms_report.py",
                  "--arm", f"iter{k:03d}={','.join(arm_dirs)}",
                  "--out", str(it_dir / "arms-report.json")])

    print(f"[selfplay] loop complete: {state['iteration']} iterations, "
          f"final ckpt {state['ckpt']}")


if __name__ == "__main__":
    main()
