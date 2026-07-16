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
    cmd = [sys.executable, "-m", "anvil.bridge.harness", "launch", "--pool",
           "--games", str(games), "--games-per-pair", str(a.games_per_pair),
           "--start-index", str(start_index), "--workers", str(a.workers),
           "--chunk", str(a.chunk), "--bridge", f"grpc:localhost:{a.port}",
           "--obs", "--census", "--purpose", purpose,
           "--seed-base", str(a.seed_base)]
    if getattr(a, "reask", False):
        cmd.append("--reask")
    _run(cmd)
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
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue  # torn tail line from a killed worker (e.g. OOM)
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
                    if r.get("reask"):
                        # re-ask rescue: a cast realized on attempt >0 —
                        # pre-reask this window would have been a forced pass
                        c["reask_rescued"] += 1
            for k in ("dropped", "forced"):
                if r.get(k):
                    c[f"combat_{k}"] += r[k]
    c["veto_rate"] = round(c["veto"] / max(1, c["veto"] + c["cast"]), 4)
    if c.get("reask_rescued") or c.get("veto"):
        # rescue rate = vetoed intents eventually realized in the same window
        c["reask_rescue_rate"] = round(c["reask_rescued"] / max(1, c["veto"]), 4)
    return dict(c)


def guard_flags(census: dict, rl: dict, baseline: dict | None,
                kl_max: float = 0.05, ent_mult: float = 2.0,
                veto_mult: float = 1.5) -> list[str]:
    """ADR-0017 halt triplines. Any non-empty result rejects the iteration's
    checkpoint and halts the loop — run-2 collapsed with every signal in
    monitor.jsonl and nothing acting on it. kl is absolute (drift per
    iteration); entropy/veto compare against the run's iter-0 baselines."""
    flags = []
    m = rl.get("mean") or {}
    kl = m.get("kl_mu")
    if kl is not None and kl > kl_max:
        flags.append(f"guard: kl_mu {kl} > {kl_max}")
    if baseline:
        ent, ent0 = m.get("ent"), baseline.get("ent")
        if ent is not None and ent0 and ent > ent_mult * ent0:
            flags.append(f"guard: ent {ent} > {ent_mult}x iter-0 ({ent0})")
        veto, veto0 = census.get("veto_rate"), baseline.get("veto_rate")
        if veto is not None and veto0 and veto > veto_mult * veto0:
            flags.append(f"guard: veto_rate {veto} > {veto_mult}x iter-0 ({veto0})")
    return flags


def _game_stats(run_dir: Path) -> dict:
    import statistics
    rows = []
    for f in run_dir.glob("workers/inv-*/games.jsonl"):
        for line in open(f):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
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
    ap.add_argument("--ent-floor", type=float, default=0.08,
                    help="hinge entropy floor passed to the learner (ADR-0017)")
    ap.add_argument("--rl-seg", type=int, default=256,
                    help="learner windows per GPU pass (rl.py --seg); halve when "
                         "cohabiting the GPU with another resident process — "
                         "activation peak scales with it, semantics don't")
    ap.add_argument("--guard-kl", type=float, default=0.05,
                    help="halt if an iteration's mean KL(pi||mu) exceeds this")
    ap.add_argument("--guard-ent-mult", type=float, default=2.0,
                    help="halt if mean entropy exceeds this multiple of iter-0")
    ap.add_argument("--guard-veto-mult", type=float, default=1.5,
                    help="halt if veto rate exceeds this multiple of iter-0")
    ap.add_argument("--value-weight", type=float, default=0.5)
    ap.add_argument("--traj-per-step", type=int, default=4)
    ap.add_argument("--arms-every", type=int, default=5,
                    help="arms vs heuristic every N iterations (0 = off)")
    ap.add_argument("--arms-pairs", default=None,
                    help="pairs file for arms runs (D8 valpair schedule)")
    ap.add_argument("--arms-games", type=int, default=200)
    ap.add_argument("--arms-seed-base", type=int, default=20260710)
    ap.add_argument("--reask", action="store_true",
                    help="re-ask-on-veto (d6-vtrace-loop §6b) for generation AND "
                         "arms — an environment change; arms are only comparable "
                         "to other -reask arms")
    args = ap.parse_args()

    # GPU cotenancy insurance (2026-07-16 OOMs beside a resident ComfyUI):
    # reclaims allocator fragmentation for this process and all subprocesses
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

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

        # ---- generate (sampled serve); idempotent — a crash later in the
        # iteration must not cost a ~25-min regeneration on resume ----
        run_dir = store = None
        for cand in sorted(glob.glob(str(RUNS_DIR / f"{purpose}-*"))):
            st = TRAJ_DIR / Path(cand).name
            if (st / "manifest.json").exists():
                run_dir, store = Path(cand), st
                print(f"[selfplay] iteration {k}: reusing {cand} (store present)")
                break
        if run_dir is None:
            mu_path = it_dir / "mu.jsonl"
            if mu_path.exists():
                mu_path.unlink()  # a fresh server APPENDS; stale records from
                # an interrupted attempt would conflict at the mu merge
            server = _start_server(state["ckpt"], args.port, it_dir / "server.log",
                                   sample=True, mu_out=mu_path,
                                   temperature=args.temperature)
            try:
                run_dir = _launch_games(purpose, args.games, state["start_index"], args)
            finally:
                _stop_server(server)

            # ---- ingest (mu joined on (g, s)) ----
            (run_dir / "mu.jsonl").write_bytes(mu_path.read_bytes())
            _run([sys.executable, "-m", "anvil.store", "ingest", str(run_dir)])
            store = TRAJ_DIR / run_dir.name
        t_gen = time.monotonic() - t_iter
        if str(store) not in state["stores"]:
            state["stores"].append(str(store))

        # ---- train (V-trace on the replay mixture) ----
        mix = state["stores"][-args.replay:]
        weights = [args.replay_weight] * (len(mix) - 1) + [args.fresh_weight]
        train_dir = it_dir / "train"
        t0 = time.monotonic()
        if (train_dir / "DONE").exists():
            print(f"[selfplay] iteration {k}: reusing completed training in {train_dir}")
        else:
            _run([sys.executable, "-m", "anvil.training.rl",
                  "--store", ",".join(mix),
                  "--weights", ",".join(map(str, weights)),
                  "--ckpt", state["ckpt"], "--out", str(train_dir),
                  "--lr", str(args.lr), "--ent-weight", str(args.ent_weight),
                  "--ent-floor", str(args.ent_floor),
                  "--value-weight", str(args.value_weight),
                  "--traj-per-step", str(args.traj_per_step),
                  "--seg", str(args.rl_seg),
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
                and abs(mean["reward"] - mean["v0"]) > 0.1:
            # §6 anomaly rule, two-sided per ADR-0017: reward >> critic is the
            # original bug-report direction; critic >> reward = value head
            # chasing clipped-rho targets (run-2 iter 5 went unflagged)
            flags.append(f"reward {mean['reward']} vs critic {mean['v0']}")
        if rl.get("tripwire_viol"):
            flags.append(f"tripwire={rl['tripwire_viol']}")
        non_won = {s: n for s, n in gstats["statuses"].items() if s != "won"}
        if sum(non_won.values()) > 0.02 * gstats["games"]:
            flags.append(f"non-decisive {non_won}")

        # ---- ADR-0017 halt guards: reject the ckpt, don't just narrate ----
        guards = guard_flags(census, rl, state.get("baseline"),
                             kl_max=args.guard_kl, ent_mult=args.guard_ent_mult,
                             veto_mult=args.guard_veto_mult)
        row = {"iteration": k, "ckpt": state["ckpt"], "run": str(run_dir),
               "store": str(store), "gen_s": round(t_gen), "train_s": round(t_train),
               "census": census, "games": gstats, "rl": rl, "flags": flags,
               "guard": guards}
        monitor.write(json.dumps(row) + "\n")
        if flags:
            print(f"[selfplay] !!! ANOMALY FLAGS iteration {k}: {flags}")
        if guards:
            (it_dir / "REJECTED").write_text("\n".join(guards) + "\n")
            print(f"[selfplay] !!! GUARD HALT iteration {k}: {guards}\n"
                  f"[selfplay] ckpt NOT accepted; loop_state unchanged; "
                  f"re-running re-evaluates the same iteration (deterministic "
                  f"halt — needs a human)")
            sys.exit(3)

        if state.get("baseline") is None:
            # the run's iter-0 operating point: the ent/veto guard baselines
            state["baseline"] = {"ent": mean.get("ent"),
                                 "veto_rate": census.get("veto_rate")}
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
                    arm_cmd = [sys.executable, "-m", "anvil.bridge.harness", "launch",
                               "--pairs-file", args.arms_pairs,
                               "--games", str(args.arms_games), "--workers",
                               str(args.workers), "--chunk", "50",
                               "--bridge", f"grpc:localhost:{args.port}",
                               "--census", "--obs", "--purpose", ap_purpose,
                               "--seed-base", str(args.arms_seed_base),
                               "--bridge-seats", str(seat)]
                    if args.reask:
                        arm_cmd.append("--reask")
                    _run(arm_cmd)
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
