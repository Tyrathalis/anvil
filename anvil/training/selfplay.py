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
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

RUNS_DIR = Path("data/runs")
TRAJ_DIR = Path("data/trajectories")


def _notify(title: str, msg: str) -> None:
    """Best-effort push for unattended runs (2026-07-23 QoL rider). Tries
    $ANVIL_NOTIFY_CMD (an executable, invoked with title and message as its
    two arguments — wire ntfy/kdeconnect/mail there), then notify-send as
    the at-desk fallback. Never raises: no notification path may kill the
    loop it exists to report on."""
    print(f"[selfplay] NOTIFY: {title} — {msg}")
    cmds = []
    if os.environ.get("ANVIL_NOTIFY_CMD"):
        cmds.append([os.environ["ANVIL_NOTIFY_CMD"], title, msg])
    cmds.append(["notify-send", "--urgency=critical", "--app-name=anvil",
                 title, msg])
    for cmd in cmds:
        if shutil.which(cmd[0]) is None:
            continue
        try:
            subprocess.run(cmd, timeout=30, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:  # noqa: BLE001
            print(f"[selfplay] notify via {cmd[0]} failed: {e}")


def _sleep_inhibitor(name: str) -> subprocess.Popen | None:
    """Driver-owned systemd-inhibit holder (2026-07-22 suspend lesson): the
    desktop must not sleep while a loop runs. The holder child gets
    PR_SET_PDEATHSIG so it dies with the driver on ANY exit path — crash,
    SIGKILL, guard halt — never orphaning a block on the user's laptop lid."""
    if shutil.which("systemd-inhibit") is None:
        return None

    def _die_with_parent() -> None:
        import ctypes
        PR_SET_PDEATHSIG = 1
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(
            PR_SET_PDEATHSIG, signal.SIGTERM)

    proc = subprocess.Popen(
        ["systemd-inhibit", "--what=sleep:idle", "--who=anvil-selfplay",
         f"--why=RL loop {name}", "--mode=block", "sleep", "infinity"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        preexec_fn=_die_with_parent)
    print(f"[selfplay] sleep inhibitor held (pid {proc.pid})")
    return proc


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


def _launch_games(purpose: str, games: int, start_index: int, a,
                  bridge_seats: "int | None" = None) -> Path:
    before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
    cmd = [sys.executable, "-m", "anvil.bridge.harness", "launch", "--pool",
           "--games", str(games), "--games-per-pair", str(a.games_per_pair),
           "--start-index", str(start_index), "--workers", str(a.workers),
           "--chunk", str(a.chunk), "--bridge", f"grpc:localhost:{a.port}",
           "--obs", "--census", "--purpose", purpose,
           "--seed-base", str(a.seed_base)]
    if bridge_seats is not None:
        # §6d mixed-opponent batch: only this seat is model-driven; the
        # other seat is the heuristic AI (the eval-arm configuration).
        cmd += ["--bridge-seats", str(bridge_seats)]
    if getattr(a, "reask", False):
        cmd.append("--reask")
    _run(cmd)
    new = set(glob.glob(str(RUNS_DIR / f"{purpose}-*"))) - before
    if len(new) != 1:
        raise RuntimeError(f"expected one new run dir for {purpose}, got {new}")
    return Path(new.pop())


def iteration_batches(name: str, k: int, games: int, heur_frac: float
                      ) -> list[tuple[str, int, int, "int | None"]]:
    """§6d generation plan for one iteration: (purpose, n_games,
    start_index_offset, bridge_seats). Mirror batch first; heuristic-opponent
    games split evenly across seat assignments for symmetry."""
    n_heur = int(round(games * heur_frac))
    h0 = n_heur // 2
    h1 = n_heur - h0
    n_mirror = games - n_heur
    out = [(f"{name}-i{k:03d}", n_mirror, 0, None)]
    if h0:
        out.append((f"{name}-i{k:03d}h0", h0, n_mirror, 0))
    if h1:
        out.append((f"{name}-i{k:03d}h1", h1, n_mirror + h0, 1))
    return out


def replay_mixture(groups: list[list[str]], replay: int,
                   fresh_weight: float, replay_weight: float
                   ) -> tuple[list[str], list[float]]:
    """Flatten the last `replay` iteration GROUPS into rl.py's store/weight
    lists: every store of the newest group gets the fresh weight, all older
    groups' stores the replay weight (§6d: the replay window is measured in
    iterations, not stores)."""
    mix_groups = groups[-replay:]
    stores = [s for grp in mix_groups for s in grp]
    n_fresh = len(mix_groups[-1])
    weights = [replay_weight] * (len(stores) - n_fresh) + [fresh_weight] * n_fresh
    return stores, weights


def _census_tallies(run_dirs) -> dict:
    """Field semantics mirror scripts/arms_report.py: priority records carry
    veto (string reason) / pick=="pass" / else cast. Accepts one run dir or a
    list (§6d iteration batch groups); the by=bridge filter keeps every rate
    model-seat-only regardless of opponent mix."""
    from collections import Counter
    dirs = run_dirs if isinstance(run_dirs, (list, tuple)) else [run_dirs]
    c: Counter[str] = Counter()
    for f in (f for rd in dirs for f in Path(rd).glob("workers/inv-*/census.jsonl")):
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
                    if not r.get("reask"):
                        c["first_veto"] += 1
                elif r.get("pick") == "pass":
                    c["pass"] += 1
                else:
                    c["cast"] += 1
                    if r.get("reask"):
                        # re-ask rescue: a cast realized on attempt >0 —
                        # pre-reask this window would have been a forced pass
                        c["reask_rescued"] += 1
                    else:
                        c["first_cast"] += 1
            for k in ("dropped", "forced"):
                if r.get(k):
                    c[f"combat_{k}"] += r[k]
    c["veto_rate"] = round(c["veto"] / max(1, c["veto"] + c["cast"]), 4)
    # M3 D1: chain-independent basis — each window contributes exactly one
    # first attempt (census "reask" marks attempts > 0 only), so re-ask chains
    # can't inflate this the way they inflate veto_rate. Done-when #1 reads it.
    c["first_veto_rate"] = round(
        c["first_veto"] / max(1, c["first_veto"] + c["first_cast"]), 4)
    if c.get("reask_rescued") or c.get("veto"):
        # rescue rate = vetoed intents eventually realized in the same window
        c["reask_rescue_rate"] = round(c["reask_rescued"] / max(1, c["veto"]), 4)
    return dict(c)


def guard_flags(census: dict, rl: dict, baseline: dict | None,
                kl_max: float = 0.05, ent_mult: float = 2.0,
                veto_mult: float = 1.5, casts_floor: float = 0.8) -> list[str]:
    """ADR-0017 halt triplines. Any non-empty result rejects the iteration's
    checkpoint and halts the loop — run-2 collapsed with every signal in
    monitor.jsonl and nothing acting on it. kl is absolute (drift per
    iteration); entropy/veto compare against the run's iter-0 baselines.
    casts_floor (§6c anti-passivity): halt if casts/game falls below this
    fraction of iter-0 — the cheapest way to zero vetoes under the
    rejected-intent penalty is to stop casting."""
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
        cpg, cpg0 = census.get("casts_per_game"), baseline.get("casts_per_game")
        if cpg is not None and cpg0 and cpg < casts_floor * cpg0:
            flags.append(f"guard: casts_per_game {cpg} < {casts_floor}x iter-0 ({cpg0})")
    return flags


def _game_stats(run_dirs) -> dict:
    import statistics
    dirs = run_dirs if isinstance(run_dirs, (list, tuple)) else [run_dirs]
    rows = []
    for f in (f for rd in dirs for f in Path(rd).glob("workers/inv-*/games.jsonl")):
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
            for k in ("reward", "v0", "v0_masked", "rho_mean", "rho_clip",
                      "kl_mu", "ent", "rej")
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
    ap.add_argument("--guard-casts-floor", type=float, default=0.8,
                    help="halt if casts/game falls below this fraction of "
                         "iter-0 (§6c anti-passivity)")
    ap.add_argument("--penalty", type=float, default=0.0,
                    help="rejected-intent penalty lambda (§6c); reward change "
                         "= RL-chain boundary — do not resume a lambda=0 "
                         "chain's replay mixture with a nonzero lambda")
    ap.add_argument("--heur-frac", type=float, default=0.0,
                    help="§6d mixed-opponent generation: fraction of each "
                         "iteration's games played vs the heuristic (split "
                         "evenly across seat assignments); 0 = pure mirror")
    ap.add_argument("--critic", default=None,
                    help="full-vis critic init ckpt (d6-vtrace-loop §6f, e.g. "
                         "data/training/d4-critic-fullvis/last.pt). Enables the "
                         "per-iteration critic phase: finetune_value --full-vis "
                         "--trainable all on the replay mixture, then rl.py "
                         "trains against the fresh critic's values. Off = v0 "
                         "masked-head bootstrap.")
    ap.add_argument("--critic-lr", type=float, default=1e-5,
                    help="critic-phase lr (low: 480-game iterations are small "
                         "for --trainable all)")
    ap.add_argument("--critic-steps", type=int, default=2000,
                    help="critic-phase steps per iteration (~1 pass over the "
                         "fresh store + replay tail at batch 256)")
    ap.add_argument("--critic-batch", type=int, default=256)
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
    ap.add_argument("--no-inhibit", action="store_true",
                    help="skip the systemd-inhibit sleep holder")
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
    if not args.no_inhibit:
        _sleep_inhibitor(args.name)  # dies with the driver (PDEATHSIG)

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
        # iteration must not cost a ~25-min regeneration on resume.
        # §6d: an iteration is 1-3 batches (mirror + heur s0/s1) with disjoint
        # start-index slices; each batch keeps its own run dir + store ----
        batches = iteration_batches(args.name, k, args.games, args.heur_frac)
        run_dirs: list = []
        for bp, _, _, _ in batches:
            found = None
            for cand in sorted(glob.glob(str(RUNS_DIR / f"{bp}-*"))):
                if (TRAJ_DIR / Path(cand).name / "manifest.json").exists():
                    found = Path(cand)
                    print(f"[selfplay] iteration {k}: reusing {cand} (store present)")
                    break
            run_dirs.append(found)
        mu_path = it_dir / "mu.jsonl"
        if any(rd is None for rd in run_dirs):
            if all(rd is None for rd in run_dirs) and mu_path.exists():
                mu_path.unlink()  # fresh iteration: a fresh server APPENDS;
                # stale records from an interrupted attempt would conflict at
                # the merge. Partial resume KEEPS the file — completed batches'
                # records live there, and regenerated batches re-emit identical
                # rows under seeded sampling.
            server = _start_server(state["ckpt"], args.port, it_dir / "server.log",
                                   sample=True, mu_out=mu_path,
                                   temperature=args.temperature)
            try:
                for j, (bp, n, off, seats) in enumerate(batches):
                    if run_dirs[j] is None:
                        run_dirs[j] = _launch_games(
                            bp, n, state["start_index"] + off, args,
                            bridge_seats=seats)
            finally:
                _stop_server(server)

        # ---- ingest (mu joined on (g, s); disjoint start-index slices make
        # the shared mu file's game ids unambiguous across batches) ----
        for rd in run_dirs:
            if not (TRAJ_DIR / rd.name / "manifest.json").exists():
                (rd / "mu.jsonl").write_bytes(mu_path.read_bytes())
                _run([sys.executable, "-m", "anvil.store", "ingest", str(rd)])
        t_gen = time.monotonic() - t_iter
        group = [str(TRAJ_DIR / rd.name) for rd in run_dirs]
        groups = [g if isinstance(g, list) else [g] for g in state["stores"]]
        if not groups or groups[-1] != group:
            groups.append(group)
        state["stores"] = groups

        mix, weights = replay_mixture(groups, args.replay,
                                      args.fresh_weight, args.replay_weight)

        # ---- critic phase (§6f): adapt the full-vis critic on the same
        # replay mixture BEFORE the policy consumes its values. Iteration 0
        # adapts the D4 critic to the self-play distribution — the designed
        # warm start. The critic path only advances in loop_state alongside
        # an ACCEPTED policy ckpt (a guard-rejected iteration rejects both).
        critic_ckpt = None
        if args.critic:
            prev_critic = state.get("critic", args.critic)
            critic_dir = it_dir / "critic"
            if (critic_dir / "DONE").exists():
                print(f"[selfplay] iteration {k}: reusing critic in {critic_dir}")
            else:
                _run([sys.executable, "-m", "anvil.training.finetune_value",
                      "--ckpt", prev_critic, "--store", ",".join(mix),
                      "--full-vis", "--trainable", "all",
                      "--lr", str(args.critic_lr),
                      "--steps", str(args.critic_steps),
                      "--warmup", "100", "--batch", str(args.critic_batch),
                      "--workers", str(args.rl_workers),
                      "--eval-every", str(args.critic_steps),
                      "--eval-batches", "50",
                      "--final-eval-batches", "50",
                      "--out", str(critic_dir)])
                if not (critic_dir / "last.pt").exists():
                    raise RuntimeError(
                        f"critic phase produced no checkpoint in {critic_dir}")
                (critic_dir / "DONE").touch()
            critic_ckpt = critic_dir / "last.pt"

        # ---- train (V-trace on the replay mixture) ----
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
                  "--penalty", str(args.penalty),
                  "--epochs", str(args.epochs), "--seed", str(k)]
                 + (["--critic-ckpt", str(critic_ckpt)] if critic_ckpt else []))
        t_train = time.monotonic() - t0
        new_ckpt = train_dir / "last.pt"
        if not new_ckpt.exists():
            raise RuntimeError(f"training produced no checkpoint at {new_ckpt}")

        # ---- monitor row + anomaly flags (accept ckpt AFTER writing it) ----
        census = _census_tallies(run_dirs)
        gstats = _game_stats(run_dirs)
        if gstats.get("games"):
            # §6c anti-passivity basis (first attempts: chain-independent)
            census["casts_per_game"] = round(
                census.get("first_cast", 0) / gstats["games"], 2)
        rl = _rl_summary(train_dir)
        flags = []
        if census.get("fallback"):
            flags.append(f"fallbacks={census['fallback']}")
        mean = rl.get("mean", {})
        if mean.get("reward") is not None and mean.get("v0") is not None:
            # §6 anomaly rule, two-sided per ADR-0017: reward >> critic is the
            # original bug-report direction; critic >> reward = value head
            # chasing clipped-rho targets (run-2 iter 5 went unflagged).
            # Basis per critic (§6f): the full-vis critic trains on RAW
            # outcomes (finetune_value BCE vs won), so its v0 compares to raw
            # reward; the masked head chases SHAPED vs targets, so it compares
            # to reward − λ·mean-rejected-per-trajectory (λ=0 ⇒ same basis).
            shaped = mean["reward"] - args.penalty * mean.get("rej", 0.0)
            v0_basis = mean["reward"] if args.critic else shaped
            if abs(v0_basis - mean["v0"]) > 0.1:
                flags.append(f"reward basis {round(v0_basis, 4)} "
                             f"(raw {mean['reward']}, rej {mean.get('rej')}) "
                             f"vs critic {mean['v0']}")
            if args.critic and mean.get("v0_masked") is not None                     and abs(shaped - mean["v0_masked"]) > 0.1:
                flags.append(f"shaped reward {round(shaped, 4)} "
                             f"vs masked head {mean['v0_masked']}")
        if rl.get("tripwire_viol"):
            flags.append(f"tripwire={rl['tripwire_viol']}")
        non_won = {s: n for s, n in gstats["statuses"].items() if s != "won"}
        if sum(non_won.values()) > 0.02 * gstats["games"]:
            flags.append(f"non-decisive {non_won}")

        # ---- ADR-0017 halt guards: reject the ckpt, don't just narrate ----
        guards = guard_flags(census, rl, state.get("baseline"),
                             kl_max=args.guard_kl, ent_mult=args.guard_ent_mult,
                             veto_mult=args.guard_veto_mult,
                             casts_floor=args.guard_casts_floor)
        row = {"iteration": k, "ckpt": state["ckpt"],
               "run": [str(rd) for rd in run_dirs],
               "store": group, "gen_s": round(t_gen), "train_s": round(t_train),
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
            _notify(f"anvil {args.name}: GUARD HALT iter {k}",
                    "; ".join(guards))
            sys.exit(3)

        if state.get("baseline") is None:
            # the run's iter-0 operating point: the ent/veto guard baselines
            state["baseline"] = {"ent": mean.get("ent"),
                                 "veto_rate": census.get("veto_rate"),
                                 "first_veto_rate": census.get("first_veto_rate"),
                                 "casts_per_game": census.get("casts_per_game")}
        state.update(iteration=k + 1, ckpt=str(new_ckpt),
                     start_index=state["start_index"] + args.games)
        if critic_ckpt is not None:
            state["critic"] = str(critic_ckpt)
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
    _notify(f"anvil {args.name}: COMPLETE",
            f"{state['iteration']} iterations, final ckpt {state['ckpt']}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # guard halts notify at the halt site
    except Exception as e:  # noqa: BLE001
        name = next((sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1])
                     if a == "--name"), "?")
        _notify(f"anvil {name}: DRIVER CRASHED", repr(e))
        raise
