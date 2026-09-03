#!/usr/bin/env python3
"""M10 reset (ADR-0094 Fork 4): the STRATIFIED PAIRED STRENGTH READ — the
primary probe read, and the day-zero read (binding execution of the
distilled planner before any training).

Population (pinned in scripts/sched_pins.py PAIRED_*): drawn ONCE from the
ADR-0078 ceiling census (user decision 2026-09-03: reuse over fresh
generation — apples-to-apples with the +14.1pp stratum number, replay parity
proven on that census); eligible turn-groups per schedule_sweep.eligible_turns
(the sweep's own rule), scored by the eval critic of record at the fork
window (the first own-turn MAIN1 dec with obs — the RolloutMonitor's fork
window); PAIRED_N windows at v < PAIRED_VMAX (primary, the funded stratum)
plus PAIRED_CONTEXT_N at v >= PAIRED_VMAX (context, never gating). Reused
for every candidate from probe7 through promotion.

Read: the sched-rollout instrument (AnvilRun -forceschedule) with NATURAL-
ONLY fork points (armId 0), K = K_ROLLS completions per window, rollSeeds
keyed on the target turn — so side A and side B share determinization and
downstream RNG per (window, roll): common random numbers, divergence only
from the policy. Side A = the candidate under BINDING execution (server
--sched-binding forks: the fork's opening seat binds, the opponent seat
advisory); side B = the same candidate under ADVISORY serve (slot tokens
fed, the cast head free — the policy as it plays today). Both sides serve
the mainline replay from the census's generating ckpt (--ckpt) and the fork
completions from the candidate (--drill-ckpt, the M4 D2.4 dual-policy
path), so the replayed prefix is identical and the fork states are the
population's.

Estimator: per window, dwr = mean over paired valid rolls of (win_A -
win_B) for the window's seat (draws/unended = non-wins for both, symmetric;
a roll whose pair is broken by a crash on either side drops); the read =
mean dwr over windows, SE = SD/sqrt(N), 95% CI, z. Reference: the K-roll
binomial floor sqrt(2 p (1-p) / K) / sqrt(N) — the paired empirical SE
sitting under it is the CRN pairing working (the M7 forced-branch read's
deliverable). Verdict vs the pre-flight bar (PAIRED_BAR): FUND = mean >= bar
AND CI excludes 0; HALT (the day-zero rule) = mean <= -bar; else FLAT.

Usage:
  uv run python scripts/sched_paired_read.py population \
      --out data/runs/sched-paired-pop
  uv run python scripts/sched_paired_read.py run \
      --plan data/runs/sched-paired-pop --name dayzero-probe6i5 \
      --ckpt-main data/training/d6-run11/iter-019/last.pt \
      --ckpt data/training/m10-probe6/iter-005/train/last.pt \
      --jar <jar> [--lanes 6] [--limit N]
  uv run python scripts/sched_paired_read.py read --run <run dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import signal
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sched_pins as pins  # noqa: E402
from schedule_sweep import eligible_turns  # noqa: E402
from veto_knowability import build_card_table  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CENSUS_STORE = REPO / "data/trajectories/m10-ceiling-census-20260825-212414"
CENSUS_PAIRS = REPO / "data/runs/m10-ceiling-census-pairs.tsv"
CEILING_FRAME = REPO / "data/runs/sched-sweep-m10/frame.json"


# ----------------------------------------------------------------- population

def population(args) -> None:
    from anvil.ante.ledger import ValueEvaluator
    from anvil.store.trajectories import TrajectoryStore

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stores = args.stores or [str(CENSUS_STORE)]
    table = build_card_table()
    rows, frame = eligible_turns(stores, table)
    print(f"eligible universe: {len(rows)} turn-groups")
    wanted: dict[str, dict[int, dict[int, dict]]] = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        wanted[r["store"]][r["g"]][r["t"]] = r

    ev = ValueEvaluator(args.critic)
    stats = Counter()
    vals: dict[tuple, float] = {}
    for store in stores:
        ts = TrajectoryStore(Path(store))
        sname = Path(store).name
        pend: list[tuple[tuple, object]] = []

        def flush():
            if not pend:
                return
            probs = ev.win_probs([e for _, e in pend])
            for (key, _), pr in zip(pend, probs):
                vals[key] = float(pr)
            pend.clear()

        for traj in ts.games(skip_undecodable=True):
            g = traj.header["g"]
            if g not in wanted[sname]:
                continue
            seen: set[int] = set()
            for i, dec in enumerate(traj.decisions):
                t = dec.get("t", 0)
                r = wanted[sname][g].get(t)
                if r is None or t in seen or dec.get("m") != "chooseSpellAbilityToPlay":
                    continue
                if dec.get("p") != r["seat"]:
                    continue
                obs = dec.get("obs")
                if not obs or obs.get("glob", {}).get("ph") != "MAIN1" \
                        or obs.get("glob", {}).get("ap") != r["seat"]:
                    continue
                seen.add(t)  # the fork window: FIRST matching dec only
                pend.append(((sname, g, t), ev.example(dec, traj.header, r["seat"],
                                                       traj.decisions[:i])))
                stats["windows"] += 1
                if len(pend) >= 256:
                    flush()
        flush()

    scored = []
    for r in rows:
        v = vals.get((r["store"], r["g"], r["t"]))
        if v is None:
            stats["missing_window"] += 1
            continue
        scored.append({"store": r["store"], "g": r["g"], "t": r["t"],
                       "seat": r["seat"], "v": round(v, 4),
                       "n_cands": len(r["cands"])})
    scored.sort(key=lambda r: (r["store"], r["g"], r["t"]))
    below = [r for r in scored if r["v"] < args.vmax]
    above = [r for r in scored if r["v"] >= args.vmax]
    print(f"scored {len(scored)}: {len(below)} below v<{args.vmax}, {len(above)} at/above")
    if len(below) < args.n:
        sys.exit(f"FATAL: below-stratum universe {len(below)} < PAIRED_N {args.n}")
    rng = random.Random(pins.PAIRED_RNG_SEED)
    primary = rng.sample(below, args.n)                       # draw 1
    context = rng.sample(above, min(args.context_n, len(above)))  # draw 2
    for r in primary:
        r["stratum"] = "below"
    for r in context:
        r["stratum"] = "context"
    pop = sorted(primary + context, key=lambda r: (r["g"], r["t"]))
    ceiling_keys = set()
    if CEILING_FRAME.exists():
        ceiling_keys = {tuple(k) for k in json.load(open(CEILING_FRAME)).get("sample_keys", [])}
    with open(out / "population.jsonl", "w") as f:
        for r in pop:
            r["in_ceiling_sample"] = (r["g"], r["t"]) in ceiling_keys
            f.write(json.dumps(r) + "\n")
    with open(out / "sched-paired.tsv", "w") as f:
        f.write(f"# ADR-0094 paired strength read population (sched_paired_read.py; "
                f"rng {pins.PAIRED_RNG_SEED}; natural-only points, horizon 0 = game end)\n")
        for r in pop:
            f.write(f"{r['g']}\t{r['t']}\t0\t{r['seat']}\t0\tauto\n")
    frame.update({
        "critic": args.critic,
        "vmax": args.vmax,
        "n_primary": len(primary),
        "n_context": len(context),
        "universe_scored": len(scored),
        "universe_below": len(below),
        "windows_scored": stats["windows"],
        "missing_window": stats["missing_window"],
        "rng_seed": pins.PAIRED_RNG_SEED,
        "bar": pins.PAIRED_BAR,
        "k_rolls": pins.K_ROLLS,
        "stores": {s: hashlib.sha256((Path(s) / "manifest.json").read_bytes()).hexdigest()[:16]
                   for s in stores},
        "seats": dict(Counter(r["seat"] for r in pop)),
        "primary_in_ceiling_sample": sum(r["in_ceiling_sample"] for r in primary),
        "v_primary_mean": round(sum(r["v"] for r in primary) / len(primary), 4),
    })
    json.dump(frame, open(out / "frame.json", "w"), indent=2)
    print(f"population -> {out}: {len(primary)} primary + {len(context)} context "
          f"(v_primary mean {frame['v_primary_mean']}, "
          f"{frame['primary_in_ceiling_sample']} in the ceiling's 600)")


# ---------------------------------------------------------------------- lanes

def _lane_scripts(run: Path, side: str, tsv_lines: list[str], n_lanes: int,
                  jar: Path, pairs: Path, port: int, heap: str) -> list[Path]:
    games = sorted({int(ln.split("\t", 1)[0]) for ln in tsv_lines})
    lane_of = {g: i % n_lanes for i, g in enumerate(games)}
    gui = jar.resolve().parent.parent.parent / "forge-gui"
    outdir = run / f"lanes-{side}"
    outdir.mkdir(exist_ok=True)
    scripts = []
    for i in range(n_lanes):
        tsv = outdir / f"lane-{i}.tsv"
        with open(tsv, "w") as f:
            for ln in tsv_lines:
                if lane_of[int(ln.split("\t", 1)[0])] == i:
                    f.write(ln + "\n")
        scratch = outdir / f"lane-{i}.scratch"
        sh = outdir / f"lane-{i}.sh"
        # replay parity with the census configuration (the sweep's lane
        # shape verbatim: -obs/-census/-paytelemetry on, scratch outputs)
        sh.write_text(
            "#!/bin/sh\nset -e\n"
            f"cd '{gui}'\n"
            f"nice -n 19 java -Xms{heap} -Xmx{heap} -XX:ActiveProcessorCount=2 "
            f"-XX:+ExitOnOutOfMemoryError "
            f"-jar '{jar.resolve()}' anvil "
            f"-pairs '{pairs.resolve()}' -gpp 5 -f Commander "
            f"-range 0 {pins.CENSUS_GAMES} -seedbase {pins.CENSUS_SEED_BASE} "
            f"-b grpc:localhost:{port} "
            f"-obs '{scratch}.obs.zst' -census '{scratch}.census.jsonl' "
            f"-paytelemetry "
            f"-rollout {pins.K_ROLLS} -labels '{outdir}/lane-{i}.out.jsonl' "
            f"-forceschedule '{tsv}'\n")
        sh.chmod(0o755)
        scripts.append(sh)
    return scripts


# ----------------------------------------------------------------------- read

def _load_side(run: Path, side: str) -> tuple[dict, Counter]:
    rows: dict[tuple, dict] = {}
    st = Counter()
    for path in sorted((run / f"lanes-{side}").glob("lane-*.out.jsonl")):
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                st["torn"] += 1
                continue
            if r.get("ev") != "sched":
                continue
            if "skip" in r:
                st["skip_" + str(r["skip"])] += 1
                continue
            if r.get("arm", 0) != 0:
                st["nonnatural_row"] += 1
                continue
            st["rows"] += 1
            if r.get("crash"):
                st["crash"] += 1
            elif not r.get("ended"):
                st["unended"] += 1
            rows[(r["i"], r["t"], r["roll"])] = r
    return rows, st


def _summ(d: list[float]) -> dict:
    n = len(d)
    if n == 0:
        return {"n": 0}
    m = sum(d) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1)) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 else float("nan")
    return {"n": n, "mean": round(m, 4), "sd": round(sd, 4), "se": round(se, 4),
            "ci95": [round(m - 1.96 * se, 4), round(m + 1.96 * se, 4)],
            "z": round(m / se, 2) if se and se > 0 else None}


def read(args) -> dict:
    run = Path(args.run)
    pop = {}
    for line in open(run / "population.jsonl"):
        r = json.loads(line)
        pop[(r["g"], r["t"])] = r
    a_rows, a_st = _load_side(run, "A")
    b_rows, b_st = _load_side(run, "B")
    bar = args.bar
    per_window = []
    drop = Counter()
    for key, r in pop.items():
        seat = r["seat"]
        diffs = []
        t_end_a, t_end_b = [], []
        for roll in range(pins.K_ROLLS):
            ra, rb = a_rows.get((key[0], key[1], roll)), b_rows.get((key[0], key[1], roll))
            if ra is None or rb is None:
                drop["missing"] += 1
                continue
            if ra.get("crash") or rb.get("crash"):
                drop["crash_pair"] += 1
                continue
            t_end_a.append(ra.get("t_end", -1))
            t_end_b.append(rb.get("t_end", -1))
            # unended (clock/horizon stop) = a draw = non-win for both sides
            wa = 1.0 if ra.get("ended") and ra.get("winner") == seat else 0.0
            wb = 1.0 if rb.get("ended") and rb.get("winner") == seat else 0.0
            if not ra.get("ended") or not rb.get("ended"):
                drop["unended_counted_as_draw"] += 1
            diffs.append((wa, wb))
        if len(diffs) < pins.MIN_VALID_ROLLS:
            drop["window_too_few_pairs"] += 1
            continue
        k = len(diffs)
        wa = sum(d[0] for d in diffs) / k
        wb = sum(d[1] for d in diffs) / k
        dd = [d[0] - d[1] for d in diffs]
        m = sum(dd) / k
        sd = math.sqrt(sum((x - m) ** 2 for x in dd) / (k - 1)) if k > 1 else 0.0
        per_window.append({
            "g": key[0], "t": key[1], "seat": seat, "v": r["v"], "stratum": r["stratum"],
            "k": k, "wr_a": wa, "wr_b": wb, "dwr": m, "pair_se": sd / math.sqrt(k),
            "t_end_a": round(sum(t_end_a) / len(t_end_a), 1),
            "t_end_b": round(sum(t_end_b) / len(t_end_b), 1),
        })

    def stratum_read(name: str) -> dict:
        ws = [w for w in per_window if w["stratum"] == name]
        if not ws:
            return {"n": 0}
        s = _summ([w["dwr"] for w in ws])
        p = (sum(w["wr_a"] for w in ws) + sum(w["wr_b"] for w in ws)) / (2 * len(ws))
        k = sum(w["k"] for w in ws) / len(ws)
        s.update({
            "wr_a": round(sum(w["wr_a"] for w in ws) / len(ws), 4),
            "wr_b": round(sum(w["wr_b"] for w in ws) / len(ws), 4),
            "k_mean": round(k, 2),
            "v_mean": round(sum(w["v"] for w in ws) / len(ws), 4),
            # the K-roll binomial floor on the per-window paired difference,
            # and the empirical per-window paired SE (CRN working = below it)
            "binomial_floor_window": round(math.sqrt(2 * p * (1 - p) / k), 4) if k else None,
            "binomial_floor_read": round(math.sqrt(2 * p * (1 - p) / k) / math.sqrt(len(ws)), 4)
            if k else None,
            "empirical_pair_se_window": round(sum(w["pair_se"] for w in ws) / len(ws), 4),
            "frac_windows_moved": round(sum(1 for w in ws if w["dwr"] != 0) / len(ws), 3),
        })
        return s

    primary = stratum_read("below")
    context = stratum_read("context")
    verdict = "NO-DATA"
    if primary.get("n"):
        m, lo, hi = primary["mean"], primary["ci95"][0], primary["ci95"][1]
        if m <= -bar:
            verdict = "HALT"      # day-zero rule: adjudication, not auto-kill
        elif m >= bar and lo > 0:
            verdict = "FUND"
        elif lo > 0:
            verdict = "POSITIVE-BELOW-BAR"
        elif hi < 0:
            verdict = "NEGATIVE-ABOVE-MINUS-BAR"
        else:
            verdict = "FLAT"
    out = {
        "run": str(run),
        "bar": bar,
        "verdict": verdict,
        "primary_v_below": primary,
        "context_v_above": context,
        "windows_read": len(per_window),
        "windows_population": len(pop),
        "drops": dict(drop),
        "side_a": dict(a_st),
        "side_b": dict(b_st),
    }
    for side in ("A", "B"):
        cp = run / f"server-{side}.counts.json"
        if cp.exists():
            c = json.load(open(cp))
            out[f"serve_{side}"] = {k: v for k, v in c.items()
                                   if "bind" in k or "fallback" in k.lower()
                                   or k.startswith("drill_sched_")}
    json.dump(out, open(run / "read.json", "w"), indent=2)
    with open(run / "read-perwindow.jsonl", "w") as f:
        for w in per_window:
            f.write(json.dumps(w) + "\n")
    p = primary
    print(f"[paired] {verdict}: primary v<{pins.PAIRED_VMAX} n={p.get('n')} "
          f"dwr {p.get('mean')} +/- {p.get('se')} (CI {p.get('ci95')}, z {p.get('z')}) "
          f"wr A {p.get('wr_a')} vs B {p.get('wr_b')}; bar {bar}; "
          f"floor {p.get('binomial_floor_read')}; "
          f"context n={context.get('n')} dwr {context.get('mean')} +/- {context.get('se')}; "
          f"drops {dict(drop)}; skips A {[k for k in a_st if k.startswith('skip')]} "
          f"B {[k for k in b_st if k.startswith('skip')]}")
    return out


# ------------------------------------------------------------------------ run

def _start_server(port: int, log: Path, ckpt_main: str, ckpt: str, binding: str,
                  counts: Path, trace: "Path | None" = None,
                  empty_rev: str = "hold") -> subprocess.Popen:
    cmd = [
        sys.executable, "-m", "anvil.bridge.server", "--mode", "model",
        "--ckpt", ckpt_main, "--drill-ckpt", ckpt, "--port", str(port),
        "--pass-delta", "0", "--sched-binding", binding, "--counts-out", str(counts),
    ]
    if trace is not None:
        cmd += ["--bind-trace", str(trace)]
    if empty_rev != "hold":
        cmd += ["--sched-empty-rev", empty_rev]
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(cmd, stdout=open(log, "w"), stderr=subprocess.STDOUT, env=env,
                            cwd=str(REPO))
    import socket

    t0 = time.monotonic()
    while time.monotonic() - t0 < 600:
        if proc.poll() is not None:
            raise RuntimeError(f"server on :{port} exited {proc.returncode}; see {log}")
        with socket.socket() as s:
            s.settimeout(0.5)
            try:
                s.connect(("127.0.0.1", port))
                return proc
            except OSError:
                time.sleep(1.0)
    proc.kill()
    raise TimeoutError(f"server on :{port} never opened")


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)  # SIGINT is ignored under detached launches
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()


def _notify(title: str, msg: str) -> None:
    try:
        from anvil.training.notify import notify

        notify(title, msg)
    except Exception:  # noqa: BLE001
        pass


def run(args) -> None:
    plan = Path(args.plan)
    jar = Path(args.jar)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = REPO / "data/runs" / f"sched-paired-{args.name}-{stamp}"
    run_dir.mkdir(parents=True)
    lines = [ln for ln in (plan / "sched-paired.tsv").read_text().splitlines()
             if ln and not ln.startswith("#")]
    pop_lines = (plan / "population.jsonl").read_text().splitlines()
    if args.limit:
        keep = {tuple(ln.split("\t")[:2]) for ln in lines[: args.limit]}
        lines = lines[: args.limit]
        pop_lines = [ln for ln in pop_lines
                     if (str(json.loads(ln)["g"]), str(json.loads(ln)["t"])) in keep]
    (run_dir / "population.jsonl").write_text("\n".join(pop_lines) + "\n")
    (run_dir / "sched-paired.tsv").write_text("\n".join(lines) + "\n")
    manifest = {
        "name": args.name, "plan": str(plan), "created": stamp,
        "ckpt_main": args.ckpt_main, "ckpt": args.ckpt,
        "jar": str(jar.resolve()),
        "jar_sha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
        "lanes_per_side": args.lanes, "heap": args.heap,
        "ports": {"A": args.port_a, "B": args.port_b},
        "empty_rev": args.empty_rev,
        "sides": {"A": "candidate, --sched-binding forks (BINDING)",
                  "B": "candidate, --sched-binding off (ADVISORY)"},
        "windows": len(lines), "k_rolls": pins.K_ROLLS, "bar": args.bar,
        "pins": {k: getattr(pins, k) for k in dir(pins) if k.startswith("PAIRED_")},
    }
    json.dump(manifest, open(run_dir / "run-manifest.json", "w"), indent=2)
    scripts = {
        side: _lane_scripts(run_dir, side, lines, args.lanes, jar, Path(args.pairs), port, args.heap)
        for side, port in (("A", args.port_a), ("B", args.port_b))
    }
    if args.watchd:
        subprocess.run([sys.executable, str(REPO / "scripts/anvil_watchd.py"), "register",
                        "--name", f"sched-paired-{args.name}", "--pid", str(os.getpid()),
                        "--dir", str(run_dir), "--stall-min", "90"], check=False)
    print(f"[paired] run {run_dir}: {len(lines)} windows x K={pins.K_ROLLS} x 2 sides, "
          f"{args.lanes} lanes/side at {args.heap}")
    servers = {}
    t0 = time.monotonic()
    try:
        servers["A"] = _start_server(args.port_a, run_dir / "server-A.log", args.ckpt_main,
                                     args.ckpt, "forks", run_dir / "server-A.counts.json",
                                     trace=(run_dir / "bind-trace-A.jsonl") if args.bind_trace else None,
                                     empty_rev=args.empty_rev)
        servers["B"] = _start_server(args.port_b, run_dir / "server-B.log", args.ckpt_main,
                                     args.ckpt, "off", run_dir / "server-B.counts.json")
        procs = []
        for side, shs in scripts.items():
            for sh in shs:
                log = sh.with_suffix(".log")
                procs.append((side, sh, subprocess.Popen(["sh", str(sh)], stdout=open(log, "w"),
                                                         stderr=subprocess.STDOUT)))
        fails = []
        for side, sh, pr in procs:
            rc = pr.wait()
            if rc != 0:
                fails.append((side, sh.name, rc))
        walls = time.monotonic() - t0
    finally:
        for pr in servers.values():
            _stop(pr)
        if args.watchd:
            subprocess.run([sys.executable, str(REPO / "scripts/anvil_watchd.py"), "unregister",
                            "--name", f"sched-paired-{args.name}"], check=False)
    manifest["wall_s"] = round(walls)
    manifest["lane_failures"] = fails
    json.dump(manifest, open(run_dir / "run-manifest.json", "w"), indent=2)
    try:
        res = read(argparse.Namespace(run=str(run_dir), bar=args.bar))
        p = res["primary_v_below"]
        _notify(f"paired read {args.name}: {res['verdict']}",
                f"dwr {p.get('mean')} +/- {p.get('se')} n={p.get('n')} "
                f"(wr A {p.get('wr_a')} / B {p.get('wr_b')}); wall {walls / 3600:.1f} h; "
                f"lane failures {len(fails)}")
    except Exception as e:  # noqa: BLE001
        _notify(f"paired read {args.name}: READ FAILED", f"{e!r} — {run_dir}")
        raise
    print(f"[paired] done in {walls / 3600:.2f} h -> {run_dir}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    sp = sub.add_parser("population")
    sp.add_argument("--stores", nargs="*", default=None)
    sp.add_argument("--out", required=True)
    sp.add_argument("--critic", default=str(REPO / pins.PAIRED_CRITIC))
    sp.add_argument("--n", type=int, default=pins.PAIRED_N)
    sp.add_argument("--context-n", type=int, default=pins.PAIRED_CONTEXT_N)
    sp.add_argument("--vmax", type=float, default=pins.PAIRED_VMAX)
    sp.set_defaults(fn=population)
    rp = sub.add_parser("run")
    rp.add_argument("--plan", required=True)
    rp.add_argument("--name", required=True)
    rp.add_argument("--ckpt-main", required=True, help="the census's generating ckpt (mainline replay)")
    rp.add_argument("--ckpt", required=True, help="the candidate (fork completions, both sides)")
    rp.add_argument("--jar", required=True)
    rp.add_argument("--pairs", default=str(CENSUS_PAIRS))
    rp.add_argument("--lanes", type=int, default=6, help="lanes PER SIDE")
    rp.add_argument("--heap", default="3g")
    rp.add_argument("--port-a", type=int, default=50091)
    rp.add_argument("--port-b", type=int, default=50092)
    rp.add_argument("--bar", type=float, default=pins.PAIRED_BAR)
    rp.add_argument("--limit", type=int, default=0, help="first N population rows only (smoke)")
    rp.add_argument("--watchd", action="store_true")
    rp.add_argument("--empty-rev", choices=["hold", "noop"], default="hold",
                    help="side A's empty-revision semantics (see server --sched-empty-rev)")
    rp.add_argument("--bind-trace", action="store_true",
                    help="side A writes one JSON line per bound window (diagnostics)")
    rp.set_defaults(fn=run)
    dp = sub.add_parser("read")
    dp.add_argument("--run", required=True)
    dp.add_argument("--bar", type=float, default=pins.PAIRED_BAR)
    dp.set_defaults(fn=read)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
