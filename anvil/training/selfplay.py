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

from anvil.training.notify import notify as _shared_notify
from anvil.training.notify import watch_register as _watch_register
from anvil.training.notify import watch_unregister as _watch_unregister

RUNS_DIR = Path("data/runs")
TRAJ_DIR = Path("data/trajectories")
REPO = Path(__file__).resolve().parents[2]


def _auto_seg(pinned: int) -> int:
    """Per-phase learner seg autotune (task #12): price GPU cotenancy at
    phase start instead of discovering it by OOM. Reads free VRAM via
    nvidia-smi (NOT torch — a CUDA context in the driver would hold ~300MB
    for the loop's lifetime, defeating the subprocess-per-phase design).
    Thresholds from the run-3 incident: seg 256 OOM'd with ~13GB free
    beside a resident ComfyUI, 128 fit. A nonzero --rl-seg pins manually;
    rl.py's OOM-halving backstops mid-phase pressure changes either way."""
    if pinned:
        return pinned
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        free_mb = int(out.stdout.split()[0])
    except Exception as e:  # noqa: BLE001
        print(f"[selfplay] seg autotune: nvidia-smi failed ({e}); using 128")
        return 128
    seg = 256 if free_mb >= 16000 else 128 if free_mb >= 9000 else 64
    print(f"[selfplay] seg autotune: {free_mb} MB free -> seg {seg}")
    return seg


def _notify(title: str, msg: str) -> None:
    """Driver-side wrapper over the shared notifier (anvil.training.notify),
    which final_read.py and any other long-running entry point also use."""
    _shared_notify(title, msg, tag="selfplay")


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
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(PR_SET_PDEATHSIG, signal.SIGTERM)

    proc = subprocess.Popen(
        [
            "systemd-inhibit",
            "--what=sleep:idle",
            "--who=anvil-selfplay",
            f"--why=RL loop {name}",
            "--mode=block",
            "sleep",
            "infinity",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=_die_with_parent,
    )
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


def _start_server(
    ckpt: str,
    port: int,
    log: Path,
    sample: bool,
    mu_out: Path | None = None,
    temperature: float = 1.0,
    drill_ckpt: str | None = None,
    drill_sample: bool = False,
    drill_mu_out: Path | None = None,
    instrument: bool = False,
):
    cmd = [
        sys.executable,
        "-m",
        "anvil.bridge.server",
        "--mode",
        "model",
        "--ckpt",
        ckpt,
        "--port",
        str(port),
        "--pass-delta",
        "0",
    ]
    if sample:
        cmd += ["--sample", "--temperature", str(temperature), "--mu-out", str(mu_out)]
    if instrument:
        # M7: sampled serving for wire-only fork sessions (no -forkobs, no
        # mu) — sampled-mainline drill maps and forced-branch instruments
        cmd += ["--fork-instrument"]
    if drill_ckpt:
        cmd += ["--drill-ckpt", drill_ckpt]
        if drill_sample:
            # M4 D3 training generation: fork completions sampled with mu,
            # mainline replay argmax on the pinned ckpt
            cmd += ["--drill-sample", "--drill-mu-out", str(drill_mu_out)]
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(cmd, stdout=open(log, "w"), stderr=subprocess.STDOUT, env=env)
    try:
        _wait_port(port)
    except TimeoutError:
        proc.kill()
        raise
    return proc


def _stop_server(proc) -> None:
    # SIGTERM, not SIGINT: under a detached launch (setsid/nohup) the server
    # inherits SIGINT=SIG_IGN, CPython never installs its KeyboardInterrupt
    # handler, and the stats + counts-dump exit path is skipped straight into
    # the 30s timeout + SIGKILL (m10-probe1 lost iteration 0's serve counters
    # this way; ADR-0085). The server's SIGTERM handler converges on the same
    # stats path by design.
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


def _run(cmd: list[str]) -> None:
    print(f"[selfplay] $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def batch_chunk(games: int, workers: int, chunk: int) -> int:
    """Per-batch chunk size: a batch that resolves to fewer than two chunks
    per worker is tail-bound — elapsed becomes the slowest worker's contiguous
    deck-pair block (an 11x finish-time spread observed in the wild; see the
    2026-08-03 bench retraction). args.chunk is a ceiling; each generation
    batch (mirror / heur splits are separate launches) shrinks it so every
    worker gets at least two rounds of refill."""
    return max(1, min(chunk, games // (2 * workers)))


def _launch_games(
    purpose: str, games: int, start_index: int, a, bridge_seats: "int | None" = None
) -> Path:
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
        str(a.games_per_pair),
        "--start-index",
        str(start_index),
        "--workers",
        str(a.workers),
        "--chunk",
        str(batch_chunk(games, a.workers, a.chunk)),
        "--bridge",
        f"grpc:localhost:{a.port}",
        "--obs",
        "--census",
        "--purpose",
        purpose,
        "--seed-base",
        str(a.seed_base),
    ]
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


def iteration_batches(
    name: str, k: int, games: int, heur_frac: float
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


def drill_slice(rows: list[dict], k: int, ppi: int) -> list[dict]:
    """Rotating per-iteration window over the drill selection: iteration k
    takes ppi rows starting at (k*ppi) mod n, wrapping — every point is
    re-drilled fresh (by the then-current ckpt) once per full cycle."""
    n = len(rows)
    start = (k * ppi) % n
    return [rows[(start + i) % n] for i in range(min(ppi, n))]


def _drill_phase(
    args,
    state: dict,
    k: int,
    drill_dir: Path,
    port: int | None = None,
    workers: int | None = None,
) -> list[str]:
    """M4 D3 drill-mixed generation: a rotating slice of the selection list
    is re-drilled — mainline replay argmax on the PINNED source ckpt (the
    only policy those games replay under), completions SAMPLED by the
    current training ckpt with mu records. Fork frames ingest as their own
    drill-provenance stores and join this iteration's store group: fresh
    now, replay-aged later, exactly like game stores. Returns store paths."""
    drill_dir.mkdir(exist_ok=True)
    rows = [json.loads(line) for line in open(args.drill_selection)]
    sl = drill_slice(rows, k, args.drill_points_per_iter)
    subset = drill_dir / "slice.jsonl"
    subset.write_text("".join(json.dumps(r) + "\n" for r in sl))
    tag = f"mix{k:03d}"
    _run(
        [
            sys.executable,
            "-m",
            "anvil.grindstone",
            "plan",
            "--curation",
            str(subset),
            "--out",
            str(drill_dir / "plan"),
            "--ckpt",
            args.drill_replay_ckpt,
            "--k",
            str(args.drill_k),
            "--anchor",
            "selected",
            "--tag",
            tag,
        ]
    )
    before = set(glob.glob(str(RUNS_DIR / f"drill{tag}-*")))
    _run(
        [
            sys.executable,
            "-m",
            "anvil.grindstone",
            "generate",
            "--manifest",
            str(drill_dir / "plan"),
            "--port",
            str(port or args.port),
            "--workers",
            str(workers or args.workers),
            "--fork-obs",
            "--sample-forks",
            "--drill-ckpt",
            state["ckpt"],
        ]
    )
    new_dirs = sorted(set(glob.glob(str(RUNS_DIR / f"drill{tag}-*"))) - before)
    if not new_dirs:
        raise RuntimeError(f"drill phase produced no run dirs (tag {tag})")
    stores = []
    for rd in new_dirs:
        _run([sys.executable, "-m", "anvil.store", "ingest", rd, "--forks"])
        stores.append(str(TRAJ_DIR / (Path(rd).name + "-forks")))
    return stores


def _seq_phase(
    args,
    state: dict,
    k: int,
    seq_dir: Path,
    drill_dir: Path,
    port: int | None = None,
    workers: int | None = None,
) -> list[str]:
    """ADR-0054 C-seq campaign: forced-seq labels (natural/hold-N/act-N × K)
    at THIS iteration's drill slice, arms answered by the CURRENT ckpt —
    labels are policy-conditional and regenerate fresh every iteration.
    Labels-only (forced-branch pin 3): L_seq's fork windows come from the
    drill phase's fork stores at the same points; both phases replay the
    mainline argmax on the pinned replay ckpt, so labels and windows
    describe the same fork states (drift = the known ~1-2% replay class,
    absorbed as label noise; unjoined points drop in seqlabels). Returns
    the campaign run dirs (seqlabels.load_rows takes them verbatim)."""
    seq_dir.mkdir(exist_ok=True)
    tag = f"seq{k:03d}"
    _run(
        [
            sys.executable,
            "-m",
            "anvil.grindstone",
            "plan",
            "--curation",
            str(drill_dir / "slice.jsonl"),
            "--out",
            str(seq_dir / "plan"),
            "--ckpt",
            args.drill_replay_ckpt,
            "--k",
            str(args.seq_k),
            "--anchor",
            "selected",
            "--tag",
            tag,
        ]
    )
    before = set(glob.glob(str(RUNS_DIR / f"drill{tag}-*")))
    _run(
        [
            sys.executable,
            "-m",
            "anvil.grindstone",
            "generate",
            "--manifest",
            str(seq_dir / "plan"),
            "--port",
            str(port or args.port),
            "--workers",
            str(workers or args.workers),
            "--force-seq",
            str(args.seq_n),
            "--drill-ckpt",
            state["ckpt"],
        ]
    )
    new_dirs = sorted(set(glob.glob(str(RUNS_DIR / f"drill{tag}-*"))) - before)
    if not new_dirs:
        raise RuntimeError(f"seq campaign produced no run dirs (tag {tag})")
    n_rows = sum(
        1 for rd in new_dirs for f in Path(rd).glob("workers/inv-*/labels.jsonl") for _ in open(f)
    )
    print(f"[selfplay] iteration {k}: seq campaign {len(new_dirs)} runs, {n_rows} label rows")
    return new_dirs


def _drill_eval_phase(args, state: dict, k: int, it_dir: Path) -> None:
    """Mid-run drill-evalset decomposition (M4, post-ADR-0031): run
    `grindstone eval` on the held-out evalset with the just-accepted
    ckpt. ADVISORY by design — mechanism-flat is a judgment, not a
    drift, so this never halts; the operator answers a flat read by
    touching <out>/STOP. Per-bin paired deltas (vs the evalset's pinned
    baseline_eval re-measurement, D2.4) land in <iter>/drill-eval.json,
    stdout, and a notify ping. monitor.jsonl stays one-row-per-iteration."""
    out = it_dir / "drill-eval.json"
    if out.exists():
        print(f"[selfplay] iteration {k}: reusing drill eval")
        return
    es = Path(args.drill_eval_set)
    before = set(es.glob("eval-*.json"))
    _run(
        [
            sys.executable,
            "-m",
            "anvil.grindstone",
            "eval",
            "--evalset",
            str(es),
            "--ckpt",
            state["ckpt"],
            "--port",
            str(args.port),
            "--workers",
            str(args.workers),
        ]
    )
    new = sorted(set(es.glob("eval-*.json")) - before)
    if not new:
        raise RuntimeError(f"drill eval wrote no report under {es}")
    rep = json.loads(new[-1].read_text())
    out.write_text(json.dumps(rep, indent=2) + "\n")
    deltas = {b: round(v["winrate"] - v["baseline"], 4) for b, v in rep["per_bin"].items()}
    print(
        f"[selfplay] iteration {k}: drill-eval paired deltas {deltas} "
        f"(overall {rep['winrate']} vs baseline {rep['baseline']})"
    )
    _notify(f"anvil {args.name}: drill-eval iter {k}", json.dumps(deltas))


def replay_mixture(
    groups: list[list[str]], replay: int, fresh_weight: float, replay_weight: float
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


def _pay_head_stats(ckpt_path) -> dict:
    """M9 D4 recipe pin 6 (second half): the payment head's own movement.

    The probe's negative branch retires the formulation, so a negative has to
    separate "the head moved and it didn't help" from "the head never moved"
    (the latter routes to dose, not to the graveyard). pay_bias starts at
    +2.0 and pay_kind_emb at exactly zero, so both series read as displacement
    from a known origin. Diagnostic only — never guarded."""
    try:
        import torch

        ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        m = ck["model"]
        from anvil.training.dataset import TASKS

        out = {}
        if "pay_bias" in m:
            out["bias"] = round(float(m["pay_bias"][TASKS["pay_class"]]), 4)
        if "pay_kind_emb.weight" in m:
            w = m["pay_kind_emb.weight"].float()
            out["kind_rms"] = round(float(w.pow(2).mean().sqrt()), 5)
        return out
    except Exception as e:  # diagnostic only — never break the loop
        return {"error": str(e)}


def _pay_drill_score(ckpt_path, drill_dir, embed, out_path) -> dict:
    """M9 D4 recipe pin 7: fold the payment-drill accuracy read into the loop.

    The observe frames are checkpoint-INDEPENDENT (the fork replayed to the
    window and banked the serve path's own option labels), so scoring an
    iteration is an offline featurize+argmax over ~290 banked frames — cheap
    enough to run every iteration, which makes the pre-registered gate
    readable live in analysis.md instead of at post-mortem. Scores the ckpt
    the iteration PRODUCED (the candidate), not the one it served."""
    d = Path(drill_dir)
    cmd = [
        "uv",
        "run",
        "python",
        str(REPO / "scripts" / "payment_drill_score.py"),
        "score",
        "--jobs",
        str(d / "observe-jobs.jsonl"),
        "--certout",
        str(d / "observe-certout.jsonl"),
        "--obs",
        *[str(x) for x in sorted(d.glob("observe-lane-*.obs.zst"))],
        "--ckpt",
        str(ckpt_path),
        "--embed",
        str(embed),
        "--out",
        str(out_path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except Exception as e:
        return {"error": str(e)}
    res: dict = {}
    for line in r.stdout.splitlines():
        t = line.split()
        # "  positive     overall: 2/64 = 0.031"
        if len(t) == 5 and t[1] == "overall:" and t[0] in ("positive", "auto_correct"):
            n, d_ = t[2].split("/")
            res[t[0]] = {"n": int(n), "d": int(d_), "acc": float(t[4])}
    if not res:
        res = {"error": (r.stderr or r.stdout)[-400:]}
    return res


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
            if r.get("m") == "payManaCost" and r.get("pick") is not None:
                # M9 rung 3 (§3c goal surface): sampled payment-deviation
                # tally — the D4 probe's cheapest signal. Argmax deviation is
                # NOT derivable here (generation samples); it rides the
                # drill-eval pass.
                c["pay_windows"] += 1
                if r.get("pick") != "auto":
                    c["pay_deviate"] += 1
                    # M9 D4 recipe pin 6: the payment head's analogue of the
                    # veto channel. The serve path reason-codes every directed
                    # execution (directed_ok / directed_salvage /
                    # directed_fail) and records the leftover float; none of it
                    # was reaching the loop. TELEMETRY ONLY — deterrence-family
                    # pricing is closed (ADR-0062) and a priced failure would
                    # confound the probe. Spikes are anomaly-set entries.
                    ex = r.get("exec")
                    if ex:
                        c[f"pay_{ex}"] += 1
                    if r.get("float_residue"):
                        c["pay_residue_windows"] += 1
                        c["pay_residue_mana"] += int(r["float_residue"])
            for k in ("dropped", "forced"):
                if r.get(k):
                    c[f"combat_{k}"] += r[k]
    c["veto_rate"] = round(c["veto"] / max(1, c["veto"] + c["cast"]), 4)
    if c["pay_windows"]:
        c["pay_deviation_rate"] = round(c["pay_deviate"] / c["pay_windows"], 4)
    if c["pay_deviate"]:
        # denominators are DEVIATIONS, not windows: auto picks never execute a
        # directed plan, so folding them in would dilute the failure signal
        # exactly where it matters (m9-plan D4 recipe pin 6).
        c["pay_fail_rate"] = round(c["pay_directed_fail"] / c["pay_deviate"], 4)
        c["pay_salvage_rate"] = round(c["pay_directed_salvage"] / c["pay_deviate"], 4)
        c["pay_residue_rate"] = round(c["pay_residue_windows"] / c["pay_deviate"], 4)
    # M3 D1: chain-independent basis — each window contributes exactly one
    # first attempt (census "reask" marks attempts > 0 only), so re-ask chains
    # can't inflate this the way they inflate veto_rate. Done-when #1 reads it.
    c["first_veto_rate"] = round(c["first_veto"] / max(1, c["first_veto"] + c["first_cast"]), 4)
    if c.get("reask_rescued") or c.get("veto"):
        # rescue rate = vetoed intents eventually realized in the same window
        c["reask_rescue_rate"] = round(c["reask_rescued"] / max(1, c["veto"]), 4)
    return dict(c)


def guard_flags(
    census: dict,
    rl: dict,
    baseline: dict | None,
    kl_max: float = 0.05,
    ent_mult: float = 2.0,
    veto_mult: float = 1.5,
    casts_floor: float = 0.8,
    seq_share_max: float | None = None,
    plan_share_max: float | None = None,
    sched_share_max: float | None = None,
    paylab_share_max: float | None = None,
    seedlab_share_max: float | None = None,
    sched_spike_mult: float | None = None,
    seedlab_spike_mult: float | None = None,
    lab_memorize_ratio: float | None = None,
    seedlab_calib_raw: float | None = None,
    paylab_calib_raw: float | None = None,
) -> list[str]:
    """ADR-0017 halt triplines. Any non-empty result rejects the iteration's
    checkpoint and halts the loop — run-2 collapsed with every signal in
    monitor.jsonl and nothing acting on it. kl is absolute (drift per
    iteration); entropy/veto compare against the run's iter-0 baselines.
    casts_floor (§6c anti-passivity): halt if casts/game falls below this
    fraction of iter-0 — the cheapest way to zero vetoes under the
    rejected-intent penalty is to stop casting."""
    flags = []
    m = rl.get("mean") or {}
    # m10-probe1 (ADR-0085): share guards read the step MEDIAN (mean
    # fallback for pre-0085 rows) — the iteration mean is spike-dominated
    # under a heavy-tailed aux CE and trips on a statistic no step ever
    # showed; the spike gets its own tripline below.
    med = rl.get("med") or {}
    kl = m.get("kl_mu")
    if kl is not None and kl > kl_max:
        flags.append(f"guard: kl_mu {kl} > {kl_max}")
    ss = med.get("seq_share", m.get("seq_share"))
    if seq_share_max is not None and ss is not None and ss > seq_share_max:
        # d6-run14: the seq term's share of PG mass is the ADR-0054
        # calibration invariant (~10%); the halt-worthy failure is the
        # term outgrowing its weight, which precedes the kl symptom
        flags.append(f"guard: seq_share {ss} > {seq_share_max}")
    ps = med.get("plan_share", m.get("plan_share"))
    if plan_share_max is not None and ps is not None and ps > plan_share_max:
        # the D6 twin of the seq-share guard: the aux term outgrowing its
        # calibrated weight precedes the kl symptom
        flags.append(f"guard: plan_share {ps} > {plan_share_max}")
    scs = med.get("sched_share", m.get("sched_share"))
    if sched_share_max is not None and scs is not None and scs > sched_share_max:
        # M10 v2 twin (same ADR-0057 invariant)
        flags.append(f"guard: sched_share {scs} > {sched_share_max}")
    pls = med.get("paylab_share", m.get("paylab_share"))
    if paylab_share_max is not None and pls is not None and pls > paylab_share_max:
        flags.append(f"guard: paylab_share {pls} > {paylab_share_max}")
    sls = med.get("seedlab_share", m.get("seedlab_share"))
    if seedlab_share_max is not None and sls is not None and sls > seedlab_share_max:
        flags.append(f"guard: seedlab_share {sls} > {seedlab_share_max}")
    if sched_spike_mult is not None:
        # the m10-probe1 disease itself: decode confidence sharpening makes
        # off-mode targets exponentially surprising (max step CE 7.7 -> 46.8
        # -> 543.5 across three iterations at a stable ~3.2 median)
        ce_max = (rl.get("spike") or {}).get("sched_ce_max")
        ce_med = med.get("sched_ce")
        if ce_max is not None and ce_med and ce_max > sched_spike_mult * ce_med:
            flags.append(
                f"guard: sched_ce_max {ce_max} > {sched_spike_mult}x median ({ce_med})"
            )
    if seedlab_spike_mult is not None:
        # ADR-0086: the spike tripline ported to the surviving CE term —
        # seedlab CE is a fixed certified batch, so a max/median blowup here
        # is head divergence, not off-mode target sampling
        sl_max = (rl.get("spike") or {}).get("seedlab_raw_max")
        sl_med = med.get("seedlab_raw")
        if sl_max is not None and sl_med and sl_max > seedlab_spike_mult * sl_med:
            flags.append(
                f"guard: seedlab_raw_max {sl_max} > {seedlab_spike_mult}x median ({sl_med})"
            )
    if lab_memorize_ratio:
        # ADR-0088 memorization tripline (re-based after the m10-probe3
        # false halt): a fixed batch FITTED is the probe2 impulse — per-step
        # raw 2.73 -> 0.18 (0.07x) within one iteration; the share guard
        # cannot see it (share decays WITH the fit). Reads the iteration
        # MINIMUM of the per-step raw vs the per-step calibration raw.
        lab_min = rl.get("min") or {}
        for key, calib in (("seedlab_raw_step", seedlab_calib_raw),
                           ("paylab_raw_step", paylab_calib_raw)):
            mv = lab_min.get(key)
            if mv is not None and calib and mv < lab_memorize_ratio * calib:
                flags.append(
                    f"guard: {key} iteration-min {mv} < "
                    f"{lab_memorize_ratio}x calib ({round(calib, 5)})"
                )
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
    return {
        "games": len(rows),
        "statuses": statuses,
        "turns_median": statistics.median(r["turns"] for r in rows) if rows else None,
        "seat0_wins": sum(
            1 for r in rows if r.get("status") == "won" and "(1)" in (r.get("winner") or "")
        ),
    }


def _rl_summary(train_dir: Path) -> dict:
    rows = [json.loads(line) for line in open(train_dir / "metrics.jsonl")]
    if not rows:
        return {}
    last = rows[-1]
    # per-key presence (not all-or-nothing): seq keys only appear after
    # iteration-0's calibration steps, and w_seq/seq_share only when the
    # C-seq term is active — a partial column still means something
    mean = {}
    for k in (
        "reward",
        "v0",
        "v0_masked",
        "rho_mean",
        "rho_clip",
        "kl_mu",
        "ent",
        "rej",
        "seq_raw",
        "seq_aux",
        "seq_share",
        # plan_share missing here made the ADR-0057 plan-share guard read
        # None forever (found at the M10 build session, 2026-08-27 — the
        # guard never could have fired across run20)
        "plan_act",
        "plan_delta",
        "plan_share",
        "sched_ce",
        "sched_live_ce",
        "sched_e",
        "sched_r",
        "sched_share",
        "paylab_raw",
        "paylab_pos",
        "paylab_auto",
        "paylab_share",
        "seedlab_raw",
        "seedlab_share",
        "seedlab_raw_step",
        "paylab_raw_step",
    ):
        vals = [r[k] for r in rows if k in r]
        if vals:
            mean[k] = round(sum(vals) / len(vals), 5)
    # ADR-0088 memorization tripline, re-based after the m10-probe3 false
    # halt: reads the PER-STEP raws (the acc[] row values are per-trajectory
    # ÷ traj_per_step — comparing those to the per-step calibration raw made
    # the guard unpassable) and the iteration MINIMUM — the discriminator
    # that separates probe2's memorization (per-step 2.73 → 0.18 = 0.07×)
    # from healthy fast learning (probe3: 2.68 → 2.11 = 0.79×)
    first = {}
    lab_min = {}
    for k in ("paylab_raw_step", "seedlab_raw_step"):
        vals = [r[k] for r in rows if k in r]
        if vals:
            first[k] = round(vals[0], 5)
            lab_min[k] = round(min(vals), 5)
    # m10-probe1 (ADR-0085): the aux-share iteration MEAN is spike-dominated
    # under a heavy-tailed aux CE (iter-2 mean share 1.50 vs median 0.18, one
    # step at sched_ce 543.5 vs median 3.2) — surface medians for the share
    # guards, and the CE max for the spike tripline.
    med = {}
    for k in (
        "seq_share",
        "plan_share",
        "sched_share",
        "paylab_share",
        "seedlab_share",
        "sched_ce",
        "seedlab_raw",
    ):
        vals = sorted(r[k] for r in rows if k in r)
        if vals:
            med[k] = round(vals[len(vals) // 2], 5)
    spike = {}
    ce_vals = [r["sched_ce"] for r in rows if "sched_ce" in r]
    if ce_vals:
        spike["sched_ce_max"] = round(max(ce_vals), 5)
    sl_vals = [r["seedlab_raw"] for r in rows if "seedlab_raw" in r]
    if sl_vals:
        spike["seedlab_raw_max"] = round(max(sl_vals), 5)
    return {
        "steps": last.get("step"),
        "traj": last.get("traj"),
        "tripwire_viol": last.get("tripwire_viol"),
        "skips": last.get("skips"),
        "mean": mean,
        "med": med,
        "spike": spike,
        "first": first,
        "min": lab_min,
        "final": last,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="V-trace self-play loop (M2 D6)")
    ap.add_argument("--name", required=True, help="loop name (dirs key off it)")
    ap.add_argument(
        "--ckpt",
        default="data/training/d5-combat/last.pt",
        help="iteration-0 init (delta=0 by design)",
    )
    ap.add_argument("--iterations", type=int, required=True)
    ap.add_argument("--games", type=int, default=480, help="games per iteration")
    ap.add_argument("--games-per-pair", type=int, default=2)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--chunk", type=int, default=30)
    ap.add_argument("--port", type=int, default=50063)
    ap.add_argument("--seed-base", type=int, required=True)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument(
        "--replay", type=int, default=4, help="stores in the training mixture (last R iterations)"
    )
    ap.add_argument(
        "--fresh-weight",
        type=float,
        default=1.0,
        help="expected passes over the newest store per iteration",
    )
    ap.add_argument(
        "--replay-weight",
        type=float,
        default=0.33,
        help="expected passes over each older store (1.0 + 3x0.33 "
        "≈ two store-scans, 50%% fresh samples)",
    )
    ap.add_argument(
        "--rl-workers",
        type=int,
        default=12,
        help="featurize workers for the learner. Was 6 while the "
        "main process was the funnel (collate ran there, so "
        "extra workers only added shm churn and 12 measured "
        "SLOWER than 6). Since worker-side collate (2026-07-26) "
        "the consumer is no longer the bottleneck and workers "
        "scale again: 2.062 -> 2.979 traj/s going 6 -> 12.",
    )
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument(
        "--pay-lr",
        type=float,
        default=None,
        help="M9 D4 (recipe pin 2): separate lr for the §3c payment params "
        "(pay_ prefix); trunk keeps --lr. At ~417 optimizer steps/iteration "
        "the fresh head cannot move at trunk lr — a probe that reads 'no "
        "movement' would be measuring the step budget, not the formulation. "
        "None = one group (v0 behavior).",
    )
    ap.add_argument(
        "--plan",
        action="store_true",
        help="M9 D6 (m9-d6-plan-latent-spec): serve the plan carry (the "
        "ckpt must be plan-grafted — d6-plan-init) and train the joint "
        "aux term; per-iteration reliance readout + kill signal armed.",
    )
    ap.add_argument(
        "--plan-lr",
        type=float,
        default=1e-3,
        help="lr group for the plan params (spec §2 — the pay-lr rationale)",
    )
    ap.add_argument(
        "--plan-proj-lr",
        type=float,
        default=1e-4,
        help="lr for the consumption proj alone (run20 iter-0 amendment: "
        "dense PG reaches it every carried window; at 1e-3 the kl guard "
        "bound at iteration 0)",
    )
    ap.add_argument("--plan-frac", type=float, default=0.1,
                    help="target aux share of PG mass (w_plan calibration)")
    ap.add_argument(
        "--plan-carry-w",
        action="store_true",
        help="carry iteration-0's w_plan for the whole run instead of the "
        "ADR-0057 default per-iteration recalibration (the --seq-carry-w "
        "twin)",
    )
    ap.add_argument(
        "--guard-plan-share",
        type=float,
        default=0.3,
        help="halt if the iteration-mean plan_share exceeds this — 3x the "
        "0.1 target (the seq-share guard twin)",
    )
    ap.add_argument(
        "--plan-reliance-store",
        default="data/trajectories/d6-run18-i000-20260821-205317",
        help="the PINNED fixed population for the per-iteration reliance "
        "readout (comparable series; day-zero banked on it)",
    )
    ap.add_argument(
        "--sched",
        action="store_true",
        help="M10 v2 schedule surface (m10-build-spec): serve the discrete "
        "schedule carry (sched-grafted ckpt), train the decode/E/R aux "
        "term, PG-mask payment windows (staged mask from birth).",
    )
    ap.add_argument("--sched-lr", type=float, default=1e-3,
                    help="lr group for the sched decode/E/R heads")
    ap.add_argument(
        "--sched-proj-lr",
        type=float,
        default=1e-4,
        help="lr for the slot-token input path (assemble.sched_*) — the "
        "run20 iter-0 lesson applied from FIRST launch (guard posture pin)",
    )
    ap.add_argument("--sched-frac", type=float, default=0.05,
                    help="target aux share of PG mass (w_sched calibration). "
                    "Post-ADR-0086 the bundle is E/R ONLY (decode CE retired); "
                    "0.05 ~= E+R's share of the old 0.1 bundle at day zero "
                    "((0.522+1.800)/(2.609+0.522+1.800)), so E/R mass carries "
                    "unchanged through the surgery")
    ap.add_argument(
        "--sched-carry-w",
        action="store_true",
        help="carry iteration-0's w_sched for the whole run (the "
        "--plan-carry-w twin; ADR-0057 default = per-iteration recalib)",
    )
    ap.add_argument(
        "--guard-sched-share",
        type=float,
        default=0.3,
        help="halt if the iteration-MEDIAN sched_share exceeds this (the "
        "plan-share guard twin; median since ADR-0085 — the mean is "
        "spike-dominated under a heavy-tailed aux CE)",
    )
    ap.add_argument(
        "--guard-sched-spike",
        type=float,
        default=100.0,
        help="halt if the iteration's max step sched_ce exceeds this multiple "
        "of the median step sched_ce (ADR-0085: the m10-probe1 decode "
        "confidence blowup — 543.5 vs median 3.2 at iteration 2, growing "
        "~e^2-3x per iteration). Inert post-ADR-0086 (sched_ce retired with "
        "the own-emission decode term); kept as the named guard class — "
        "the seedlab twin below covers the surviving CE term",
    )
    ap.add_argument(
        "--sched-reliance-store",
        default="data/trajectories/m10-reliance-pop-20260827",
        help="the PINNED fixed population for the per-iteration v2 "
        "sched-reliance readout (fresh graft-era generation, seed base "
        "20530827; day-zero presence floor banked on it)",
    )
    ap.add_argument(
        "--pay-labels",
        default=None,
        help="M10 R5: certified payment evalset dir for the supervised "
        "class-CE aux (ADR-0075/0082) — with --sched this is the pay "
        "head's only training signal (PG mask). Never the holdout dir.",
    )
    ap.add_argument(
        "--pay-observe",
        default=None,
        help="observe-frames dir for --pay-labels (post-boundary sv=2)",
    )
    ap.add_argument("--paylab-frac", type=float, default=0.1,
                    help="target pay-label share of PG mass (w_paylab calibration)")
    ap.add_argument(
        "--paylab-carry-w",
        action="store_true",
        help="carry iteration-0's w_paylab for the whole run (the "
        "--plan-carry-w twin)",
    )
    ap.add_argument(
        "--guard-paylab-share",
        type=float,
        default=0.3,
        help="halt if the iteration-mean paylab_share exceeds this",
    )
    ap.add_argument(
        "--seed-labels",
        default=None,
        help="M10 R5: minted best-arm seed labels (decode-CE enrichment)",
    )
    ap.add_argument(
        "--seed-store",
        default=None,
        help="the ceiling census store the seed labels rejoin against",
    )
    ap.add_argument("--seedlab-frac", type=float, default=0.05,
                    help="target seed-label share of PG mass. ADR-0088: 0.05 "
                    "= the retired own-emission term's EFFECTIVE decode mass "
                    "(0.1 x its ~53% share of the day-zero bundle) — the mass "
                    "that drove content_flip 0.0138 in probe1; ADR-0086's 0.1 "
                    "doubled it into the probe2 impulse")
    ap.add_argument(
        "--seedlab-carry-w",
        action="store_true",
        help="carry iteration-0's w_seedlab for the whole run (the "
        "--paylab-carry-w twin). ADR-0088: ON in the recipe for BOTH "
        "fixed-batch terms — per-invocation recalibration against a "
        "partially-fitted batch is the cross-iteration amplifier (probe1 "
        "w_seedlab grew 12x over three iterations)",
    )
    ap.add_argument(
        "--lab-k", type=int, default=0,
        help="ADR-0088: apply the fixed pay/seed label batches one k-window "
        "chunk per optimizer step (epoch-shuffled, without replacement) "
        "instead of full-batch — forwarded to rl.py. 0 = legacy",
    )
    ap.add_argument(
        "--lab-warmup", type=int, default=0,
        help="ADR-0088: linear warmup ramp (applied steps) on both "
        "fixed-batch terms' weights — forwarded to rl.py. 0 = off",
    )
    ap.add_argument(
        "--guard-lab-memorize",
        type=float,
        default=0.25,
        help="ADR-0088 memorization tripline (re-based after the m10-probe3 "
        "false halt): halt if a fixed-batch term's iteration-MINIMUM "
        "per-step raw (seedlab_raw_step/paylab_raw_step) falls below this "
        "fraction of its per-step raw-at-calibration — a fitted batch is "
        "the probe2 signature (per-step 2.73 -> 0.18 = 0.07x in one "
        "iteration) while healthy fast learning sits far above it (probe3 "
        "iter 0: 0.79x). The share guard is structurally blind to fitting "
        "(share decays WITH the fit). 0 disables",
    )
    ap.add_argument(
        "--guard-seedlab-share",
        type=float,
        default=0.3,
        help="halt if the iteration-MEDIAN seedlab_share exceeds this (3x "
        "target; median per ADR-0085, mean fallback for pre-0085 rows)",
    )
    ap.add_argument(
        "--guard-seedlab-spike",
        type=float,
        default=100.0,
        help="halt if the iteration's max step seedlab_raw exceeds this "
        "multiple of its median (the --guard-sched-spike twin ported to the "
        "surviving CE term at ADR-0086 — confidence blowup is a property of "
        "any aux CE, not of the retired term)",
    )
    ap.add_argument("--ent-weight", type=float, default=3e-3)
    ap.add_argument(
        "--ent-floor",
        type=float,
        default=0.08,
        help="hinge entropy floor passed to the learner (ADR-0017)",
    )
    ap.add_argument(
        "--rl-seg",
        type=int,
        default=0,
        help="learner windows per GPU pass (rl.py --seg); "
        "activation peak scales with it, semantics don't. "
        "0 (default) = autotune per phase from free VRAM "
        "(task #12); nonzero pins it manually",
    )
    ap.add_argument(
        "--guard-kl",
        type=float,
        default=0.05,
        help="halt if an iteration's mean KL(pi||mu) exceeds this",
    )
    ap.add_argument(
        "--guard-ent-mult",
        type=float,
        default=2.0,
        help="halt if mean entropy exceeds this multiple of iter-0",
    )
    ap.add_argument(
        "--guard-veto-mult",
        type=float,
        default=1.5,
        help="halt if veto rate exceeds this multiple of iter-0",
    )
    ap.add_argument(
        "--guard-casts-floor",
        type=float,
        default=0.8,
        help="halt if casts/game falls below this fraction of iter-0 (§6c anti-passivity)",
    )
    ap.add_argument(
        "--guard-seq-share",
        type=float,
        default=0.3,
        help="halt if the iteration-mean seq_share (w_seq*|L_seq| / "
        "mean|PG per traj|) exceeds this — 3x the ADR-0054 target "
        "share of 0.1. The d6-run14 guard: the term outgrowing its "
        "frozen weight is the cause; kl growth is the symptom.",
    )
    ap.add_argument(
        "--seq-margin",
        type=float,
        default=6.0,
        help="passed to rl.py --seq-margin (hinge on the L_seq contrast; "
        "d6-run14). Recorded here so launch commands pin it.",
    )
    ap.add_argument(
        "--seq-carry-w",
        action="store_true",
        help="calibrate w_seq at run start only and carry it (the "
        "ADR-0054 behavior; reproduces run14/run15). Default: "
        "recalibrate every iteration (ADR-0057 — tracks declining PG "
        "mass so seq_share holds ~seq_frac instead of drifting).",
    )
    ap.add_argument(
        "--penalty",
        type=float,
        default=0.0,
        help="rejected-intent penalty lambda (§6c); reward change "
        "= RL-chain boundary — do not resume a lambda=0 "
        "chain's replay mixture with a nonzero lambda. "
        "ADR-0054 pricing = 0.01 with grouping 'first'.",
    )
    ap.add_argument(
        "--penalty-grouping",
        choices=["first", "event"],
        default="first",
        help="§6c pricing basis (ADR-0054): first = one penalty per veto "
        "window; event = the superseded per-attempt pricing",
    )
    ap.add_argument(
        "--seq-n",
        type=int,
        default=0,
        help="ADR-0054 C-seq campaign horizon N (0 = campaign off). "
        "Requires the drill phase (--drill-selection): the campaign "
        "rides the drill slice — the drill fork stores supply L_seq's "
        "windows, the forced-seq labels its targets. Recipe note: "
        "the bundle run sizes --drill-points-per-iter to the campaign "
        "P (~100), not run13's 15.",
    )
    ap.add_argument(
        "--seq-k",
        type=int,
        default=16,
        help="completions per forced-seq arm (ADR-0054: 16 — freshness "
        "beats K=32 precision on policy-conditional labels)",
    )
    ap.add_argument(
        "--drill-windows-only",
        action="store_true",
        help="recipe pin 2026-08-12: drill fork stores serve ONLY as "
        "L_seq window sources, never the training mixture — the "
        "bundle is the sole training-signal delta (run12/13 read "
        "supplementation TIE; ADR-0049 says it was never the "
        "missing signal). Pairs with --drill-k 2.",
    )
    ap.add_argument(
        "--overlap-campaign",
        action="store_true",
        help="run generation ‖ (drill → campaign) concurrently — both "
        "tracks serve ckpt_k so the trained gradient is recipe-"
        "identical to sequential; pure wall-clock overlap (~25%%). "
        "Fleet interference is measured, not assumed: per-track "
        "walls land in the monitor row.",
    )
    ap.add_argument(
        "--campaign-port",
        type=int,
        default=0,
        help="drill/campaign server port (default port+2; must differ "
        "from --port when --overlap-campaign)",
    )
    ap.add_argument(
        "--campaign-workers",
        type=int,
        default=0,
        help="drill/campaign fleet width (default = --workers). The "
        "2026-08-12 w-bench: single-fleet throughput peaks at w=24 "
        "and regresses at 32 on the 32-core box — under "
        "--overlap-campaign keep gen+campaign totals near 24 "
        "(e.g. gen 8 + campaign 16, campaign = the critical path)",
    )
    ap.add_argument(
        "--heur-frac",
        type=float,
        default=0.0,
        help="§6d mixed-opponent generation: fraction of each "
        "iteration's games played vs the heuristic (split "
        "evenly across seat assignments); 0 = pure mirror",
    )
    ap.add_argument(
        "--critic",
        default=None,
        help="full-vis critic init ckpt (d6-vtrace-loop §6f, e.g. "
        "data/training/d4-critic-fullvis/last.pt). Enables the "
        "per-iteration critic phase: finetune_value --full-vis "
        "--trainable all on the replay mixture, then rl.py "
        "trains against the fresh critic's values. Off = v0 "
        "masked-head bootstrap.",
    )
    ap.add_argument(
        "--critic-lr",
        type=float,
        default=1e-5,
        help="critic-phase lr (low: 480-game iterations are small for --trainable all)",
    )
    ap.add_argument(
        "--critic-steps",
        type=int,
        default=2000,
        help="critic-phase steps per iteration (~1 pass over the "
        "fresh store + replay tail at batch 256)",
    )
    ap.add_argument("--critic-batch", type=int, default=256)
    ap.add_argument("--value-weight", type=float, default=0.5)
    ap.add_argument("--traj-per-step", type=int, default=4)
    ap.add_argument(
        "--arms-every", type=int, default=5, help="arms vs heuristic every N iterations (0 = off)"
    )
    ap.add_argument(
        "--arms-pairs", default=None, help="pairs file for arms runs (D8 valpair schedule)"
    )
    ap.add_argument("--arms-games", type=int, default=200)
    ap.add_argument("--arms-seed-base", type=int, default=20260710)
    ap.add_argument(
        "--drill-selection",
        default=None,
        help="drill-mixed generation (M4 D3): selection.jsonl "
        "from `grindstone select` (holdout already "
        "subtracted there)",
    )
    ap.add_argument(
        "--drill-points-per-iter",
        type=int,
        default=15,
        help="rotating slice size; f = ppi*K / (games + ppi*K)",
    )
    ap.add_argument("--drill-k", type=int, default=8, help="sampled completions per drill point")
    ap.add_argument(
        "--pay-drill-dir",
        default=None,
        help="M9 D4 (recipe pin 7): observe-artifact directory of the payment "
        "drill evalset (observe-jobs.jsonl + observe-certout.jsonl + "
        "observe-lane-*.obs.zst). Set = score every iteration's produced ckpt "
        "against the pre-registered gate; the frames are ckpt-independent so "
        "this is an offline featurize+argmax, not a replay.",
    )
    ap.add_argument(
        "--pay-drill-embed",
        default=None,
        help="embedding dir for --pay-drill-dir scoring (the ckpt's own embed)",
    )
    ap.add_argument(
        "--drill-replay-ckpt",
        default=None,
        help="PINNED mainline replay ckpt (the source games' "
        "generator; required with --drill-selection)",
    )
    ap.add_argument(
        "--drill-eval-set",
        default=None,
        help="held-out drill evalset dir (grindstone evalset) for "
        "the mid-run decomposition phase — advisory per-bin "
        "reads; requires --drill-eval-every",
    )
    ap.add_argument(
        "--drill-eval-every",
        type=int,
        default=0,
        help="run the drill-eval phase every N iterations "
        "(0 = off; 10 = iters 9 and 19 on a 20-iter run — "
        "the halfway kill/continue read + the closing read)",
    )
    ap.add_argument(
        "--reask",
        action="store_true",
        help="re-ask-on-veto (d6-vtrace-loop §6b) for generation AND "
        "arms — an environment change; arms are only comparable "
        "to other -reask arms",
    )
    ap.add_argument(
        "--no-inhibit", action="store_true", help="skip the systemd-inhibit sleep holder"
    )
    args = ap.parse_args()
    if args.pay_drill_dir and not args.pay_drill_embed:
        ap.error("--pay-drill-dir requires --pay-drill-embed (the ckpt's embedding dir)")
    if args.drill_selection and not args.drill_replay_ckpt:
        ap.error(
            "--drill-selection requires --drill-replay-ckpt (the pinned source-game generator)"
        )
    if bool(args.drill_eval_set) != bool(args.drill_eval_every):
        ap.error("--drill-eval-set and --drill-eval-every go together")

    # GPU cotenancy insurance (2026-07-16 OOMs beside a resident ComfyUI):
    # reclaims allocator fragmentation for this process and all subprocesses
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    out = Path("data/training") / args.name
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "loop_state.json"
    state = (
        json.loads(state_path.read_text())
        if state_path.exists()
        else {"iteration": 0, "ckpt": args.ckpt, "stores": [], "start_index": 0}
    )
    # Line-buffer our own narration: under a detached launch (stdout -> log
    # file) block buffering held EVERY driver print in memory for run-8's
    # whole 36h — "===== iteration" markers, guard text — starving the log
    # watcher; subprocess output interleaved fine (own fds). Found 2026-07-25.
    sys.stdout.reconfigure(line_buffering=True)
    monitor = open(out / "monitor.jsonl", "a", buffering=1)
    (out / "loop_config.json").write_text(json.dumps(vars(args), indent=2))
    if not args.no_inhibit:
        _sleep_inhibitor(args.name)  # dies with the driver (PDEATHSIG)
    # Self-registration with the standing watcher: the driver reports its
    # OWN pid (never pattern-derived — the pgrep self-match class).
    # Deliberate exits unregister; a crash leaves the registration so the
    # watcher fires GONE within a tick.
    _watch_register(args.name, out)

    while state["iteration"] < args.iterations:
        if (out / "STOP").exists():
            print("[selfplay] STOP file present — exiting between iterations")
            _watch_unregister(args.name)
            return
        k = state["iteration"]
        it_dir = out / f"iter-{k:03d}"
        it_dir.mkdir(exist_ok=True)
        print(f"\n[selfplay] ===== iteration {k}: ckpt={state['ckpt']} =====")

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
        walls = {"gen": 0.0, "campaign": 0.0}

        def _gen_track() -> None:
            t0 = time.monotonic()
            if any(rd is None for rd in run_dirs):
                if all(rd is None for rd in run_dirs) and mu_path.exists():
                    mu_path.unlink()  # fresh iteration: a fresh server APPENDS;
                    # stale records from an interrupted attempt would conflict
                    # at the merge. Partial resume KEEPS the file — completed
                    # batches' records live there, and regenerated batches
                    # re-emit identical rows under seeded sampling.
                server = _start_server(
                    state["ckpt"],
                    args.port,
                    it_dir / "server.log",
                    sample=True,
                    mu_out=mu_path,
                    temperature=args.temperature,
                )
                try:
                    for j, (bp, n, off, seats) in enumerate(batches):
                        if run_dirs[j] is None:
                            run_dirs[j] = _launch_games(
                                bp, n, state["start_index"] + off, args, bridge_seats=seats
                            )
                finally:
                    _stop_server(server)
            # ---- ingest (mu joined on (g, s); disjoint start-index slices
            # make the shared mu file's game ids unambiguous across batches)
            for rd in run_dirs:
                if not (TRAJ_DIR / rd.name / "manifest.json").exists():
                    (rd / "mu.jsonl").write_bytes(mu_path.read_bytes())
                    _run([sys.executable, "-m", "anvil.store", "ingest", str(rd)])
            walls["gen"] = time.monotonic() - t0

        def _campaign_track() -> tuple[list[str], list[str]]:
            # ---- drill phase (M4 D3) + C-seq campaign (ADR-0054), both
            # phase-idempotent. Under --drill-windows-only the fork stores
            # serve ONLY as L_seq window sources (never the mixture) — the
            # drill phase can then run at K=2 ----
            t0 = time.monotonic()
            dstores: list[str] = []
            sruns: list[str] = []
            camp_port = args.campaign_port or (args.port + 2)
            camp_w = args.campaign_workers or args.workers
            if args.drill_selection:
                stores_rec = it_dir / "drill" / "stores.json"
                if stores_rec.exists():
                    dstores = json.loads(stores_rec.read_text())
                    print(f"[selfplay] iteration {k}: reusing drill stores")
                else:
                    dstores = _drill_phase(
                        args, state, k, it_dir / "drill", port=camp_port, workers=camp_w
                    )
                    stores_rec.write_text(json.dumps(dstores))
            if args.seq_n:
                if not args.drill_selection:
                    raise RuntimeError(
                        "--seq-n requires --drill-selection (the campaign rides the drill slice)"
                    )
                seq_rec = it_dir / "seq" / "runs.json"
                if seq_rec.exists():
                    sruns = json.loads(seq_rec.read_text())
                    print(f"[selfplay] iteration {k}: reusing seq campaign")
                else:
                    sruns = _seq_phase(
                        args,
                        state,
                        k,
                        it_dir / "seq",
                        it_dir / "drill",
                        port=camp_port,
                        workers=camp_w,
                    )
                    seq_rec.write_text(json.dumps(sruns))
            walls["campaign"] = time.monotonic() - t0
            return dstores, sruns

        if args.overlap_campaign and args.drill_selection:
            # gen ‖ (drill → campaign): both tracks serve ckpt_k, so the
            # trained gradient is recipe-identical to sequential — pure
            # wall-clock overlap. Campaign servers live on their own port;
            # fleet interference is a MEASURED question (per-track walls
            # land in the monitor row for the battery to read).
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=2) as pool:
                f_gen = pool.submit(_gen_track)
                f_camp = pool.submit(_campaign_track)
                f_gen.result()
                drill_stores, seq_runs = f_camp.result()
        else:
            _gen_track()
            drill_stores, seq_runs = _campaign_track()
        t_gen = walls["gen"]

        # windows-only (recipe pin 2026-08-12): drill fork stores stay OUT
        # of the training mixture — the bundle is the only training-signal
        # delta vs the base recipe; fork frames exist for L_seq windows
        mixture_drill = [] if args.drill_windows_only else drill_stores
        group = [str(TRAJ_DIR / rd.name) for rd in run_dirs] + mixture_drill
        groups = [g if isinstance(g, list) else [g] for g in state["stores"]]
        if not groups or groups[-1] != group:
            groups.append(group)
        state["stores"] = groups

        mix, weights = replay_mixture(groups, args.replay, args.fresh_weight, args.replay_weight)

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
                _run(
                    [
                        sys.executable,
                        "-m",
                        "anvil.training.finetune_value",
                        "--ckpt",
                        prev_critic,
                        "--store",
                        ",".join(mix),
                        "--full-vis",
                        "--trainable",
                        "all",
                        "--lr",
                        str(args.critic_lr),
                        "--steps",
                        str(args.critic_steps),
                        "--warmup",
                        "100",
                        "--batch",
                        str(args.critic_batch),
                        "--workers",
                        str(args.rl_workers),
                        "--eval-every",
                        str(args.critic_steps),
                        "--eval-batches",
                        "50",
                        "--final-eval-batches",
                        "50",
                        "--out",
                        str(critic_dir),
                    ]
                    # C2a (ADR-0054): drilled-point wr_K aux into the critic
                    # phase — the channel that reaches pass-A values
                    + (
                        ["--seq-labels", ",".join(seq_runs), "--seq-stores", ",".join(drill_stores)]
                        if seq_runs and drill_stores
                        else []
                    )
                )
                if not (critic_dir / "last.pt").exists():
                    raise RuntimeError(f"critic phase produced no checkpoint in {critic_dir}")
                (critic_dir / "DONE").touch()
            critic_ckpt = critic_dir / "last.pt"

        # ---- train (V-trace on the replay mixture) ----
        train_dir = it_dir / "train"
        t0 = time.monotonic()
        if (train_dir / "DONE").exists():
            print(f"[selfplay] iteration {k}: reusing completed training in {train_dir}")
        else:
            _run(
                [
                    sys.executable,
                    "-m",
                    "anvil.training.rl",
                    "--store",
                    ",".join(mix),
                    "--weights",
                    ",".join(map(str, weights)),
                    "--ckpt",
                    state["ckpt"],
                    "--out",
                    str(train_dir),
                    "--lr",
                    str(args.lr),
                    *(["--pay-lr", str(args.pay_lr)] if args.pay_lr is not None else []),
                    # D6 plan latent (m9-d6-plan-latent-spec): carry + joint
                    # aux; w_plan calibrated once at iteration 0 and carried
                    # via loop_state (the --seq-w lesson)
                    *(
                        [
                            "--plan",
                            "--plan-lr",
                            str(args.plan_lr),
                            "--plan-proj-lr",
                            str(args.plan_proj_lr),
                            *(
                                ["--plan-w", str(state["plan_w"])]
                                if state.get("plan_w")
                                else ["--plan-frac", str(args.plan_frac)]
                            ),
                        ]
                        if args.plan
                        else []
                    ),
                    # M10 v2 schedule surface (m10-build-spec): decode/E/R
                    # aux + discrete carry + the PG staged pay mask, from
                    # birth; w_sched carried via loop_state like w_plan
                    *(
                        [
                            "--sched",
                            "--pay-pg-mask",
                            "--sched-lr",
                            str(args.sched_lr),
                            "--sched-proj-lr",
                            str(args.sched_proj_lr),
                            *(
                                ["--sched-w", str(state["sched_w"])]
                                if state.get("sched_w")
                                else ["--sched-frac", str(args.sched_frac)]
                            ),
                        ]
                        if args.sched
                        else []
                    ),
                    # M10 R5: the supervised conditional pay labels (the pay
                    # head's only signal under the PG mask)
                    *(
                        [
                            "--pay-labels",
                            args.pay_labels,
                            "--pay-observe",
                            args.pay_observe,
                            *(
                                ["--paylab-w", str(state["paylab_w"])]
                                if state.get("paylab_w")
                                else ["--paylab-frac", str(args.paylab_frac)]
                            ),
                        ]
                        if args.pay_labels
                        else []
                    ),
                    *(
                        [
                            "--seed-labels",
                            args.seed_labels,
                            "--seed-store",
                            args.seed_store,
                            *(
                                ["--seedlab-w", str(state["seedlab_w"])]
                                if state.get("seedlab_w")
                                else ["--seedlab-frac", str(args.seedlab_frac)]
                            ),
                        ]
                        if args.seed_labels
                        else []
                    ),
                    # ADR-0088 fixed-batch mechanics (subsample + warmup)
                    "--lab-k",
                    str(args.lab_k),
                    "--lab-warmup",
                    str(args.lab_warmup),
                    "--ent-weight",
                    str(args.ent_weight),
                    "--ent-floor",
                    str(args.ent_floor),
                    "--value-weight",
                    str(args.value_weight),
                    "--traj-per-step",
                    str(args.traj_per_step),
                    "--seg",
                    str(_auto_seg(args.rl_seg)),
                    "--workers",
                    str(args.rl_workers),
                    "--penalty",
                    str(args.penalty),
                    "--penalty-grouping",
                    args.penalty_grouping,
                    "--epochs",
                    str(args.epochs),
                    "--seed",
                    str(k),
                ]
                + (["--critic-ckpt", str(critic_ckpt)] if critic_ckpt else [])
                # C-seq (ADR-0054): this iteration's fresh labels + the drill
                # fork stores that carry the matching fork windows
                + (
                    [
                        "--seq-labels",
                        ",".join(seq_runs),
                        "--seq-stores",
                        ",".join(drill_stores),
                        "--seq-margin",
                        str(args.seq_margin),
                    ]
                    if seq_runs and drill_stores
                    else []
                )
                + (["--seq-w", str(state["seq_w"])] if seq_runs and state.get("seq_w") else [])
                # in-phase abort at 5x the iteration-mean guard (d6-run14:
                # the runaway crossed 5x guard ~40% into the phase)
                + (["--kl-abort", str(5 * args.guard_kl)] if args.guard_kl > 0 else [])
            )
        t_train = time.monotonic() - t0
        new_ckpt = train_dir / "last.pt"
        if not new_ckpt.exists():
            raise RuntimeError(f"training produced no checkpoint at {new_ckpt}")

        # ---- monitor row + anomaly flags (accept ckpt AFTER writing it) ----
        census = _census_tallies(run_dirs)
        gstats = _game_stats(run_dirs)
        if gstats.get("games"):
            # §6c anti-passivity basis (first attempts: chain-independent)
            census["casts_per_game"] = round(census.get("first_cast", 0) / gstats["games"], 2)
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
                flags.append(
                    f"reward basis {round(v0_basis, 4)} "
                    f"(raw {mean['reward']}, rej {mean.get('rej')}) "
                    f"vs critic {mean['v0']}"
                )
            if (
                args.critic
                and mean.get("v0_masked") is not None
                and abs(shaped - mean["v0_masked"]) > 0.1
            ):
                flags.append(f"shaped reward {round(shaped, 4)} vs masked head {mean['v0_masked']}")
        if rl.get("tripwire_viol"):
            flags.append(f"tripwire={rl['tripwire_viol']}")
        non_won = {s: n for s, n in gstats["statuses"].items() if s != "won"}
        if sum(non_won.values()) > 0.02 * gstats["games"]:
            flags.append(f"non-decisive {non_won}")

        # ---- ADR-0017 halt guards: reject the ckpt, don't just narrate ----
        # ADR-0088: raw-at-calibration per fixed-batch term — this
        # iteration's calibration json when it recalibrated, else the
        # iteration-0 value carried in loop_state (the carry-w path)
        def _calib_raw(name: str, key: str) -> float | None:
            p = train_dir / f"{name}_calibration.json"
            if p.exists():
                return json.loads(p.read_text()).get(key)
            return state.get(f"{name}_calib_raw")

        guards = guard_flags(
            census,
            rl,
            state.get("baseline"),
            kl_max=args.guard_kl,
            ent_mult=args.guard_ent_mult,
            veto_mult=args.guard_veto_mult,
            casts_floor=args.guard_casts_floor,
            seq_share_max=args.guard_seq_share,
            plan_share_max=args.guard_plan_share if args.plan else None,
            sched_share_max=args.guard_sched_share if args.sched else None,
            paylab_share_max=args.guard_paylab_share if args.pay_labels else None,
            seedlab_share_max=args.guard_seedlab_share if args.seed_labels else None,
            sched_spike_mult=args.guard_sched_spike if args.sched else None,
            seedlab_spike_mult=args.guard_seedlab_spike if args.seed_labels else None,
            lab_memorize_ratio=args.guard_lab_memorize or None,
            seedlab_calib_raw=(
                _calib_raw("seedlab", "seedlab_raw_at_calib") if args.seed_labels else None
            ),
            paylab_calib_raw=(
                _calib_raw("paylab", "paylab_raw_at_calib") if args.pay_labels else None
            ),
        )
        row = {
            "iteration": k,
            "ckpt": state["ckpt"],
            "run": [str(rd) for rd in run_dirs],
            "store": group,
            "gen_s": round(t_gen),
            "campaign_s": round(walls["campaign"]),
            "train_s": round(t_train),
            "census": census,
            "games": gstats,
            "rl": rl,
            "flags": flags,
            "guard": guards,
        }
        # ---- M9 D4 payment probe readouts (pins 6-7): head movement from its
        # known init, and the drill accuracy of the ckpt this iteration
        # produced. Both diagnostic — the gate is adjudicated at the read
        # session, nothing here auto-promotes or halts ----
        pay_head = _pay_head_stats(new_ckpt)
        if pay_head:
            row["pay_head"] = pay_head
        if args.pay_drill_dir:
            row["pay_drills"] = _pay_drill_score(
                new_ckpt, args.pay_drill_dir, args.pay_drill_embed, it_dir / "pay-drills.jsonl"
            )
            print(f"[selfplay] pay drills iteration {k}: {row['pay_drills']}")
        # ---- M9 D6 reliance readout (spec §6, per iteration, fixed
        # population) — diagnostic in the row; the KILL SIGNAL (spec §7,
        # numerics pinned at the recipe session) is the ONLY reader that
        # acts, and only from accepted-iteration 4 on ----
        if args.plan:
            rel_out = it_dir / "plan-reliance.json"
            subprocess.run(
                [
                    sys.executable, "scripts/plan_reliance.py",
                    "--ckpt", str(new_ckpt),
                    "--store", args.plan_reliance_store,
                    "--out", str(rel_out),
                ],
                check=False,
            )
            if rel_out.exists():
                row["plan_reliance"] = json.loads(rel_out.read_text())
                print(f"[selfplay] plan reliance iteration {k}: "
                      f"flip {row['plan_reliance']['argmax_flip']} "
                      f"bce {row['plan_reliance']['aux_act_bce']} "
                      f"rms {row['plan_reliance']['plan_rms']}")
        # ---- M10 v2 telemetry (m10-build-spec §5): family 1 = the
        # sched_reliance instrument on the pinned population; families 2/3 =
        # the SchedServe counters dumped beside the mu file at server stop.
        # Diagnostic in the row; the kill/FUND numerics session pins the
        # only acting reader. ----
        if args.sched:
            counts_path = Path(str(mu_path) + ".counts.json")
            if counts_path.exists():
                sc = json.loads(counts_path.read_text())
                row["sched_serve"] = {
                    k_: v for k_, v in sc.items() if k_.startswith("sched_")
                }
            srel_out = it_dir / "sched-reliance.json"
            subprocess.run(
                [
                    sys.executable, "scripts/sched_reliance.py",
                    "--ckpt", str(new_ckpt),
                    "--store", args.sched_reliance_store,
                    "--out", str(srel_out),
                ],
                check=False,
            )
            if srel_out.exists():
                row["sched_reliance"] = json.loads(srel_out.read_text())
                print(f"[selfplay] sched reliance iteration {k}: "
                      f"flip {row['sched_reliance']['argmax_flip']} "
                      f"content {row['sched_reliance']['content_flip']} "
                      f"ce {row['sched_reliance']['aux_ce']} "
                      f"rms {row['sched_reliance']['sched_rms']}")
        monitor.write(json.dumps(row) + "\n")
        # ---- standing analysis battery (run-analysis-protocol.md): cheap
        # per-iteration pass — monitor curves + the holding row. Diagnostic
        # only; battery.emit never raises into the loop ----
        from anvil.evals import battery

        battery_an = battery.emit(battery.per_iteration, out, group) or []
        if battery_an:
            print(f"[selfplay] battery anomalies iteration {k}: {battery_an}")
        if flags:
            print(f"[selfplay] !!! ANOMALY FLAGS iteration {k}: {flags}")
        if guards:
            (it_dir / "REJECTED").write_text("\n".join(guards) + "\n")
            print(
                f"[selfplay] !!! GUARD HALT iteration {k}: {guards}\n"
                f"[selfplay] ckpt NOT accepted; loop_state unchanged; "
                f"re-running re-evaluates the same iteration (deterministic "
                f"halt — needs a human)"
            )
            _notify(f"anvil {args.name}: GUARD HALT iter {k}", "; ".join(guards))
            _watch_unregister(args.name)  # deliberate exit — no GONE alert
            sys.exit(3)

        if state.get("baseline") is None:
            # the run's iter-0 operating point: the ent/veto guard baselines
            state["baseline"] = {
                "ent": mean.get("ent"),
                "veto_rate": census.get("veto_rate"),
                "first_veto_rate": census.get("first_veto_rate"),
                "casts_per_game": census.get("casts_per_game"),
                # M9 D4: the live-window pay_deviation baseline the plan calls
                # for (no pre-run number exists for it). RECORD-ONLY — the
                # deviation tripwire is an anomaly-set entry, never a guard
                # (rung-3 pin); guard_flags does not read this key.
                "pay_deviation_rate": census.get("pay_deviation_rate"),
            }
        state.update(
            iteration=k + 1, ckpt=str(new_ckpt), start_index=state["start_index"] + args.games
        )
        if critic_ckpt is not None:
            state["critic"] = str(critic_ckpt)
        # w_seq recalibrates PER ITERATION by default (ADR-0057, d6-run15:
        # PG mass declines as training proceeds while the hinged L_seq does
        # not, so a frozen run-start w_seq lets seq_share drift toward the
        # guard with no seq-term misbehavior; per-iteration calibration
        # tracks PG mass by construction — safe now that the hinge bounds
        # |L_seq|, which was the run14 precondition failure). --seq-carry-w
        # restores the ADR-0054 run-start-only behavior (era reproduction
        # of run14/run15). Cost of recalibrating: each iteration's first
        # --seq-calib-steps optimizer steps run seq-off (~6% at run scale).
        cal_path = train_dir / "seq_calibration.json"
        if args.seq_carry_w and seq_runs and "seq_w" not in state and cal_path.exists():
            state["seq_w"] = json.loads(cal_path.read_text())["w_seq"]
            print(f"[selfplay] w_seq calibrated at run start: {state['seq_w']:.6g} (carried)")
        pcal_path = train_dir / "plan_calibration.json"
        if args.plan_carry_w and args.plan and "plan_w" not in state and pcal_path.exists():
            state["plan_w"] = json.loads(pcal_path.read_text())["w_plan"]
            print(f"[selfplay] w_plan calibrated at run start: {state['plan_w']:.6g} (carried)")
        scal_path = train_dir / "sched_calibration.json"
        if args.sched_carry_w and args.sched and "sched_w" not in state and scal_path.exists():
            state["sched_w"] = json.loads(scal_path.read_text())["w_sched"]
            print(f"[selfplay] w_sched calibrated at run start: {state['sched_w']:.6g} (carried)")
        plcal_path = train_dir / "paylab_calibration.json"
        if (args.paylab_carry_w and args.pay_labels and "paylab_w" not in state
                and plcal_path.exists()):
            plcal = json.loads(plcal_path.read_text())
            state["paylab_w"] = plcal["w_paylab"]
            # ADR-0088: the honest (iteration-0) raw rides loop_state so the
            # memorization guard keeps its reference once recalibration stops
            state["paylab_calib_raw"] = plcal["paylab_raw_at_calib"]
            print(f"[selfplay] w_paylab calibrated at run start: {state['paylab_w']:.6g} (carried)")
        slcal_path = train_dir / "seedlab_calibration.json"
        if (args.seedlab_carry_w and args.seed_labels and "seedlab_w" not in state
                and slcal_path.exists()):
            slcal = json.loads(slcal_path.read_text())
            state["seedlab_w"] = slcal["w_seedlab"]
            state["seedlab_calib_raw"] = slcal["seedlab_raw_at_calib"]
            print(f"[selfplay] w_seedlab calibrated at run start: "
                  f"{state['seedlab_w']:.6g} (carried)")
        # ---- D6 KILL SIGNAL (spec §7, recipe-session numerics): from the
        # 4th ACCEPTED iteration, if the carry has never flipped ≥0.5% of
        # carried argmax decisions AND the aux act-BCE has plateaued
        # (< 2% relative improvement over the last two accepted
        # iterations), the formulation is dead — halt, record, notify ----
        if args.plan and "plan_reliance" in row:
            series = state.setdefault("plan_reliance_series", [])
            series.append({
                "iteration": k,
                "argmax_flip": row["plan_reliance"]["argmax_flip"],
                "aux_act_bce": row["plan_reliance"]["aux_act_bce"],
            })
            if len(series) >= 4:
                max_flip = max(s["argmax_flip"] for s in series)
                bce_now = series[-1]["aux_act_bce"]
                bce_prev2 = series[-3]["aux_act_bce"]
                if max_flip < 0.005 and bce_now > 0.98 * bce_prev2:
                    msg = (
                        f"PLAN KILL (spec §7): max argmax_flip {max_flip:.4f} < 0.005 "
                        f"over {len(series)} accepted iterations AND aux plateaued "
                        f"(bce {bce_now:.4f} vs {bce_prev2:.4f} two iterations back)"
                    )
                    (it_dir / "PLAN-KILL").write_text(msg + "\n")
                    state_path.write_text(json.dumps(state, indent=2))
                    print(f"[selfplay] !!! {msg}")
                    _notify(f"anvil {args.name}: PLAN KILL iter {k}", msg)
                    _watch_unregister(args.name)
                    sys.exit(4)
        state_path.write_text(json.dumps(state, indent=2))

        # ---- arms (argmax serve, paired seeds, both seat assignments) ----
        if args.arms_every and (k + 1) % args.arms_every == 0 and args.arms_pairs:
            arm_dirs = []
            server = _start_server(
                state["ckpt"], args.port, it_dir / "arms-server.log", sample=False
            )
            try:
                for seat in (0, 1):
                    ap_purpose = f"{args.name}-arm-i{k:03d}-s{seat}"
                    before = set(glob.glob(str(RUNS_DIR / f"{ap_purpose}-*")))
                    arm_cmd = [
                        sys.executable,
                        "-m",
                        "anvil.bridge.harness",
                        "launch",
                        "--pairs-file",
                        args.arms_pairs,
                        "--games",
                        str(args.arms_games),
                        "--workers",
                        str(args.workers),
                        "--chunk",
                        "50",
                        "--bridge",
                        f"grpc:localhost:{args.port}",
                        "--census",
                        "--obs",
                        "--purpose",
                        ap_purpose,
                        "--seed-base",
                        str(args.arms_seed_base),
                        "--bridge-seats",
                        str(seat),
                    ]
                    if args.reask:
                        arm_cmd.append("--reask")
                    _run(arm_cmd)
                    new = set(glob.glob(str(RUNS_DIR / f"{ap_purpose}-*"))) - before
                    arm_dirs.append(new.pop())
            finally:
                _stop_server(server)
            _run(
                [
                    sys.executable,
                    "scripts/arms_report.py",
                    "--arm",
                    f"iter{k:03d}={','.join(arm_dirs)}",
                    "--out",
                    str(it_dir / "arms-report.json"),
                ]
            )

        # ---- mid-run drill-evalset decomposition (advisory; own server) ----
        if args.drill_eval_every and (k + 1) % args.drill_eval_every == 0:
            _drill_eval_phase(args, state, k, it_dir)

    print(f"[selfplay] loop complete: {state['iteration']} iterations, final ckpt {state['ckpt']}")
    # ---- run-end battery: full curves + holding trajectory + behavioral
    # delta (init vs final). The anomaly lines ride the COMPLETE notify so
    # the report gets read by default (run-analysis-protocol rule 2) ----
    from anvil.evals import battery

    end_an = battery.emit(battery.run_end, out) or []
    an_txt = "; ".join(end_an) if end_an else "none"
    _notify(
        f"anvil {args.name}: COMPLETE",
        f"{state['iteration']} iterations, final ckpt {state['ckpt']}; "
        f"battery anomalies: {an_txt} (report {out / 'analysis' / 'analysis.md'})",
    )
    _watch_unregister(args.name)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # guard halts notify at the halt site
    except Exception as e:  # noqa: BLE001
        name = next((sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == "--name"), "?")
        _notify(f"anvil {name}: DRIVER CRASHED", repr(e))
        raise
