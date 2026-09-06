#!/usr/bin/env python3
"""M11 Build 0 — the CRITIC-LOOKAHEAD reliability read (m11-plan.md build 0;
adjudicates Fork C). Question: does a critic valuing the state AFTER an
option is applied rank the certifier's options the way K=8 two-turn rollouts
rank them? If yes, "copy, apply one option, evaluate" (~1/16 of a rollout
label's cost) becomes the training-time labeler for most windows.

Mechanics (the retest lane, plus recording): the harvest's rolled-out windows
replay through -forceschedule with their own sched_arms, K = the pinned 8
rolls, horizon 2 — and -forkobs, so EVERY completion's decision windows
stream to a fork store (arm-aware synthetic ids; "a" in the fork header).
The read values each completion at two horizons from the directed seat's
perspective, with two critics:
  eot  = the first priority window of turn t+1 (the arm's turn is over; the
         cheap labeler's horizon — one copy, one turn)
  h2   = the last window before the horizon stop (the composite's horizon)
  fullvis = d4-critic-fullvis (the critic of record, ADR-0015; the
            training-time labeler candidate)
  masked  = the policy ckpt's own value head (the only critic a deployment
            could use; a separate reliability read, named at ADR-0097)
Score per arm = mean over rolls of V(arm, r) - V(natural, r), paired by roll
seed (common determinization). Target = the pinned h2 composite per arm,
mean over the 8 rolls (sched_pins.composite, payer perspective vs natural).

PRE-REGISTERED (2026-09-05, user-adjudicated) on the headline cell
"fullvis / eot / K=1 (roll 0) vs the 8-roll composite", mean within-window
Spearman over windows with >= 3 scored arms:
  >= 0.40  ADOPT  — critic lookahead labels most windows; rollouts certify the
                    pivotality-aimed stratum only
  0.20-0.40 HYBRID — critic aims/pre-filters; rollouts stay the label of record
  <  0.20  RETIRE — rollouts only; lookahead survives as a deployment-gate question
(Label reliability at K=8 is 0.66, so the observable ceiling is ~0.8; the
label's own split-half is 0.50 and the frozen-trunk scorer probe read 0.08.)
Diagnostic cells: K=8 (roll variance vs horizon), h2 (does the critic agree
with the composite at the composite's own horizon), split-roll cells against
the label's own split-half on the same sample (cost-matched comparators).

Usage:
  uv run python scripts/critic_lookahead_read.py run --name cl1 --n 200 [--lanes 8] [--dry-run]
  uv run python scripts/critic_lookahead_read.py run --name cl2 --all
  uv run python scripts/critic_lookahead_read.py read --run data/runs/critic-lookahead-cl1
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
from sched_certify_finish import load_arms  # noqa: E402
from schedule_read import load_rows  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data/runs/sched-harvest-h1/harvest-manifest.json"
CKPT_MAIN = "data/training/d6-run11/iter-019/train/last.pt"
CKPT_FULLVIS = "data/training/d4-critic-fullvis/last.pt"
SAMPLE_SEED = 20260905
BARS = {"adopt": 0.40, "hybrid": 0.20}
ROLLS = tuple(range(pins.K_ROLLS))


# ---------------------------------------------------------------- run

def _windows_all() -> list[dict]:
    m = json.loads(MANIFEST.read_text())
    rows = []
    for b in m["batches"]:
        spread_path = b["labels"].replace(".jsonl", ".spread.jsonl")
        for ln in open(spread_path):
            s = json.loads(ln)
            rows.append({"run": b["run"], "store": b["store"], "g": s["g"], "t": s["t"],
                         "seat": s["seat"], "certified_h1": bool(s.get("certified")),
                         "n_arms_h1": len(s["arms"])})
    return rows


def run(args) -> None:
    out = REPO / "data/runs" / f"critic-lookahead-{args.name}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "lanes").mkdir(exist_ok=True)
    rows = _windows_all()
    if not args.all:
        rng = random.Random(SAMPLE_SEED)
        rows = rng.sample(rows, min(args.n, len(rows)))
    by_run: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_run[r["run"]].append(r)
    jar = sorted((REPO.parent / "forge/forge-gui-desktop/target").glob("*-jar-with-dependencies.jar"),
                 key=lambda p: p.stat().st_mtime)[-1]
    gui = jar.parent.parent.parent / "forge-gui"
    fork_commit = subprocess.run(["git", "-C", str(REPO.parent / "forge"), "rev-parse", "HEAD"],
                                 capture_output=True, text=True).stdout.strip()
    fork_dirty = bool(subprocess.run(["git", "-C", str(REPO.parent / "forge"), "status", "--short"],
                                     capture_output=True, text=True).stdout.strip())
    run_id = f"critic-lookahead-{args.name}"
    manifest = {"name": args.name, "run_id": run_id, "created": time.strftime("%Y%m%d-%H%M%S"),
                "jar": str(jar), "jar_sha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
                "fork_commit": fork_commit, "fork_dirty": fork_dirty, "k": pins.K_ROLLS,
                "sample_seed": None if args.all else SAMPLE_SEED, "bars": BARS,
                "windows": [], "runs": {}, "lanes": []}
    lanes = []
    lane_no = 0
    for run_dir, rs in by_run.items():
        rd = Path(run_dir)
        rj = json.loads((rd / "run.json").read_text())
        arms = load_arms([str(rd / "workers" / "inv-*" / "labels.jsonl")])
        lines = []
        for r in rs:
            ent = arms.get((r["g"], r["t"]))
            if ent is None:
                continue
            base = f"{r['g']}\t{r['t']}\t{ent['horizon']}\t{ent['seat']}"
            for arm_id, (mode, labels) in sorted(ent["arms"].items()):
                tail = ("\t" + "\t".join(labels)) if labels else ""
                lines.append(f"{base}\t{arm_id}\t{mode}{tail}")
            manifest["windows"].append({**r, "horizon": ent["horizon"]})
        n_lanes = max(1, round(args.lanes * len(rs) / len(rows)))
        games = sorted({int(ln.split("\t", 1)[0]) for ln in lines})
        lane_of = {g: i % n_lanes for i, g in enumerate(games)}
        tag = rd.name.split("-")[3]  # bNN
        manifest["runs"][run_dir] = {"windows": len(rs), "lanes": n_lanes,
                                     "range": [rj["start_index"], rj["games"]]}
        for i in range(n_lanes):
            wdir = out / "workers" / f"inv-{lane_no:04d}"
            wdir.mkdir(parents=True, exist_ok=True)
            tsv = out / "lanes" / f"lane-{tag}-{i}.tsv"
            with open(tsv, "w") as f:
                for ln in lines:
                    if lane_of[int(ln.split("\t", 1)[0])] == i:
                        f.write(ln + "\n")
            sh = out / "lanes" / f"lane-{tag}-{i}.sh"
            labels_out = out / "lanes" / f"lane-{tag}-{i}.out.jsonl"
            # the harvest run's own replay parameters; -forkobs streams the
            # completions to workers/inv-N/obs-forks.zst (ingest --forks);
            # the sched labels stay OUTSIDE workers/ (ingest's labels
            # cross-check assumes plain rollout rows).
            sh.write_text(
                "#!/bin/sh\nset -e\n"
                f"cd '{gui}'\n"
                f"nice -n 19 java -Xms{args.heap} -Xmx{args.heap} -XX:ActiveProcessorCount=2 "
                f"-XX:+ExitOnOutOfMemoryError -jar '{jar}' anvil "
                f"-pairs '{rd / rj['pairs_file']}' -gpp {rj['games_per_pair']} -f Commander "
                f"-range {rj['start_index']} {rj['games']} -seedbase {rj['seed_base']} "
                f"-b grpc:localhost:{args.port} "
                f"-obs '{wdir}/obs.zst' -census '{wdir}/census.jsonl' -forkobs "
                f"{'-reask ' if rj.get('reask') else ''}"
                f"-rollout {pins.K_ROLLS} -labels '{labels_out}' "
                f"-forceschedule '{tsv}'\n")
            sh.chmod(0o755)
            lanes.append(sh)
            manifest["lanes"].append({"sh": str(sh), "worker": str(wdir), "tsv": str(tsv),
                                      "labels": str(labels_out), "n_lines": sum(1 for _ in open(tsv))})
            lane_no += 1
    harvest_manifest = json.loads((Path(rows[0]["store"]) / "manifest.json").read_text())
    (out / "run.json").write_text(json.dumps({
        "run_id": run_id, "purpose": "m11-build0-critic-lookahead", "created": manifest["created"],
        "fork_commit": fork_commit, "fork_dirty": fork_dirty, "jar": str(jar),
        "jar_sha256": manifest["jar_sha256"], "protocol_version": 0,
        "pool_version": harvest_manifest.get("pool_version"), "format": "Commander",
        "bridge": f"grpc:localhost:{args.port}", "rollout_k": pins.K_ROLLS, "fork_obs": True,
        "tags": "critic-lookahead", "windows": len(manifest["windows"]),
    }, indent=2) + "\n")
    json.dump(manifest, open(out / "lookahead-manifest.json", "w"), indent=2)
    print(f"[lookahead] {len(manifest['windows'])} windows over {len(lanes)} lanes -> {out}")
    if args.dry_run:
        print("[lookahead] dry run: lane scripts written, nothing launched")
        return
    # server: the harvest's serving config (sampled, fork-instrument)
    scmd = [sys.executable, "-m", "anvil.bridge.server", "--mode", "model", "--ckpt", CKPT_MAIN,
            "--port", str(args.port), "--pass-delta", "0", "--sample", "--temperature", "1.0",
            "--mu-out", str(out / "serve-mu.jsonl"), "--fork-instrument",
            "--counts-out", str(out / "server.counts.json")]
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    # watchd registration (stall = no artifact under the run dir for 30 min;
    # completion rows land every few seconds while lanes are healthy)
    subprocess.run([sys.executable, str(REPO / "scripts/anvil_watchd.py"), "register",
                    "--name", run_id, "--pid", str(os.getpid()), "--dir", str(out),
                    "--stall-min", "30"], check=False)
    server = subprocess.Popen(scmd, stdout=open(out / "server.log", "w"), stderr=subprocess.STDOUT,
                              env=env, cwd=str(REPO))
    import socket
    t0 = time.monotonic()
    while True:
        if server.poll() is not None:
            raise RuntimeError("server died")
        with socket.socket() as s:
            s.settimeout(0.5)
            try:
                s.connect(("127.0.0.1", args.port))
                break
            except OSError:
                time.sleep(1)
        if time.monotonic() - t0 > 600:
            raise TimeoutError("server never opened")
    procs = [subprocess.Popen(["sh", str(sh)], stdout=open(sh.with_suffix(".log"), "w"),
                              stderr=subprocess.STDOUT) for sh in lanes]
    (out / "lanes.pid").write_text("\n".join(str(p.pid) for p in procs) + f"\nserver {server.pid}\n")
    fails = [sh.name for sh, p in zip(lanes, procs) if p.wait() != 0]
    if server.poll() is None:
        server.send_signal(signal.SIGTERM)
        try:
            server.wait(timeout=60)
        except subprocess.TimeoutExpired:
            server.kill()
    manifest["lane_failures"] = fails
    manifest["wall_s"] = round(time.monotonic() - t0)
    json.dump(manifest, open(out / "lookahead-manifest.json", "w"), indent=2)
    print(f"[lookahead] lanes done in {(time.monotonic() - t0) / 60:.1f} min, failures {fails}")
    res = ingest_and_read(out)
    try:
        from anvil.training.notify import notify
        notify(f"critic-lookahead {args.name} read",
               f"{res['n_windows_read']} windows; headline Spearman {res['headline'].get('spearman_mean')} "
               f"-> {res['verdict']}; lane failures {fails}; {manifest['wall_s'] // 60} min")
    except Exception as e:  # noqa: BLE001
        print(f"[lookahead] notify failed: {e}")
    subprocess.run([sys.executable, str(REPO / "scripts/anvil_watchd.py"), "unregister",
                    "--name", run_id], check=False)


def ingest_and_read(out: Path) -> dict:
    from anvil.store.trajectories import ingest
    dest = REPO / "data/trajectories" / f"{out.name}-forks"
    if not (dest / "manifest.json").exists():
        ingest(out, dest, forks=True)
    return read(argparse.Namespace(run=str(out), store=str(dest), limit=None))


# ---------------------------------------------------------------- read

def spearman(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 3:
        return float("nan")
    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else float("nan")


def _auc(scores: list[float], y: list[int]) -> float:
    pos = [s for s, t in zip(scores, y) if t]
    neg = [s for s, t in zip(scores, y) if not t]
    if not pos or not neg:
        return float("nan")
    return sum((1.0 if a > b else 0.5 if a == b else 0.0) for a in pos for b in neg) / (len(pos) * len(neg))


def _certified(entry: dict, seat: int) -> bool:
    """The pinned adjudication on the lane's own rolls (select 0-3, score 4-7)."""
    from schedule_read import arm_scores
    cands = []
    for arm_id, rows in sorted(entry["arms"].items()):
        if any(r.get("void") for r in rows.values()):
            continue
        s = arm_scores(rows, entry["nat"], seat, pins.SELECT_ROLLS)
        c = arm_scores(rows, entry["nat"], seat, pins.SCORE_ROLLS)
        if len(s) < pins.MIN_VALID_ROLLS or len(c) < pins.MIN_VALID_ROLLS:
            continue
        cands.append((sum(s) / len(s), -arm_id, c))
    if not cands:
        return False
    cands.sort(reverse=True)
    c = cands[0][2]
    mean = sum(c) / len(c)
    agree = sum(1 for x in c if (x > 0) == (mean > 0)) / len(c)
    return mean >= pins.THETA and agree >= pins.CONSISTENT


class Critic:
    """ValueEvaluator with the fork frame's own serve-time history (the wire
    composite the featurizer ships) instead of a store-side reconstruction."""

    def __init__(self, ckpt: str, full_vis: bool | None):
        from anvil.ante.ledger import ValueEvaluator
        self.ev = ValueEvaluator(str(REPO / ckpt), full_vis=full_vis)

    def example(self, dec: dict, header: dict, perspective: int) -> dict:
        import numpy as np
        import torch

        from anvil.bridge.featurize import wire_history
        from anvil.encoder.transform import HISTORY_K, assemble
        ev = self.ev
        out = assemble(dec, header, perspective=perspective,
                       history=wire_history(dec.get("hist"), perspective), full_vis=ev.full_vis)
        ex = ev.example(dec, header, perspective, [])  # pads + tensors; history overwritten below
        row_of = out["entity_row_of"]
        hist = np.full((HISTORY_K, 3), -1, dtype=np.int64)
        for j, h in enumerate(out["history"][-HISTORY_K:]):
            hist[j] = (ev.methods.id(h["m"]), h["self"], row_of.get(h["e"], -1))
        ex["history"] = torch.from_numpy(hist)
        return ex

    def values(self, exs: list[dict]) -> list[float]:
        if not exs:
            return []
        return [float(v) for v in self.ev.win_probs(exs)]


def _pick_windows(decs: list[dict], tt: int) -> dict[str, dict | None]:
    """eot = first obs-carrying decision of turn tt+1; h2 = last obs-carrying
    decision of the completion (the horizon stop fires at TurnBegan(tt+3))."""
    eot = None
    last = None
    for d in decs:
        obs = d.get("obs")
        if not obs:
            continue
        turn = obs.get("glob", {}).get("turn", -1)
        if eot is None and turn >= tt + 1:
            eot = d
        last = d
    return {"eot": eot, "h2": last}


def read(args) -> dict:
    out = Path(args.run)
    man = json.loads((out / "lookahead-manifest.json").read_text())
    store_dir = Path(args.store) if args.store else REPO / "data/trajectories" / f"{out.name}-forks"
    from anvil.store.trajectories import TrajectoryStore
    st = TrajectoryStore(store_dir)
    rows = load_rows([str(out / "lanes" / "lane-*.out.jsonl")])
    tally: Counter = Counter()
    # completions: (pg, tt) -> (arm, roll) -> traj
    comp: dict[tuple, dict[tuple, object]] = defaultdict(dict)
    for traj in st.games(skip_undecodable=True):
        fk = traj.header.get("fork") or {}
        if "a" not in fk:
            tally["frame_no_arm"] += 1
            continue
        comp[(fk["pg"], fk["tt"])][(fk["a"], fk["r"])] = traj
    critics = {"fullvis": Critic(CKPT_FULLVIS, None), "masked": Critic(CKPT_MAIN, False)}
    # gather examples per critic, evaluate in one batch each
    pending: dict[str, list[dict]] = {c: [] for c in critics}
    slots: dict[str, list[tuple]] = {c: [] for c in critics}   # (win_i, arm, roll, horizon)
    windows = []
    for w in man["windows"]:
        if args.limit and len(windows) >= args.limit:
            break
        key = (w["g"], w["t"])
        entry = rows.get(key)
        if entry is None or entry["skips"]:
            tally["window_skipped_or_missing"] += 1
            continue
        comps = comp.get(key, {})
        seat = w["seat"]
        win_i = len(windows)
        rec = {**w, "vals": {c: {} for c in critics}, "comp": {}, "void": [], "certified_lane": _certified(entry, seat)}
        # composites per (arm, roll), the label's own axes
        for arm_id, arows in sorted(entry["arms"].items()):
            if any(r.get("void") for r in arows.values()):
                rec["void"].append(arm_id)
                continue
            for roll, r in arows.items():
                n = entry["nat"].get(roll)
                if n is None or r.get("crash") or n.get("crash") or "snap" not in r or "snap" not in n:
                    continue
                rec["comp"][f"{arm_id}:{roll}"] = pins.composite(pins.axes(r, seat), pins.axes(n, seat))
        # critic values per (arm, roll, horizon), natural included (arm 0)
        for (arm_id, roll), traj in comps.items():
            if arm_id in rec["void"]:
                continue
            lab = entry["nat"].get(roll) if arm_id == 0 else entry["arms"].get(arm_id, {}).get(roll)
            if lab is None or lab.get("crash"):
                continue
            picks = _pick_windows(traj.decisions, w["t"])
            for hz, dec in picks.items():
                for c, cr in critics.items():
                    if dec is None:
                        # no window at/after the horizon: the completion ended
                        # inside the arm's turn -> the outcome IS the value
                        if lab.get("ended") and lab.get("winner", -1) >= 0:
                            rec["vals"][c][f"{arm_id}:{roll}:{hz}"] = 1.0 if lab["winner"] == seat else 0.0
                        else:
                            tally[f"no_{hz}_window"] += 1
                        continue
                    try:
                        pending[c].append(cr.example(dec, traj.header, seat))
                    except Exception as e:  # noqa: BLE001
                        tally[f"featurize_fail_{type(e).__name__}"] += 1
                        continue
                    slots[c].append((win_i, arm_id, roll, hz))
        windows.append(rec)
    for c, cr in critics.items():
        t0 = time.time()
        vals = cr.values(pending[c])
        for (win_i, arm_id, roll, hz), v in zip(slots[c], vals):
            windows[win_i]["vals"][c][f"{arm_id}:{roll}:{hz}"] = v
        print(f"[lookahead] {c}: {len(vals)} states valued in {time.time() - t0:.0f}s", flush=True)

    # ---- cells
    def pred(rec, c, hz, roll_set):
        """per arm: mean over rolls of V(arm) - V(nat), rolls where both exist"""
        outp = {}
        for arm_id in sorted({int(k.split(':')[0]) for k in rec["comp"]}):
            ds = []
            for r in roll_set:
                a = rec["vals"][c].get(f"{arm_id}:{r}:{hz}")
                n = rec["vals"][c].get(f"0:{r}:{hz}")
                if a is not None and n is not None:
                    ds.append(a - n)
            if ds:
                outp[arm_id] = sum(ds) / len(ds)
        return outp

    def target(rec, roll_set):
        outp = {}
        for arm_id in sorted({int(k.split(':')[0]) for k in rec["comp"]}):
            cs = [rec["comp"][f"{arm_id}:{r}"] for r in roll_set if f"{arm_id}:{r}" in rec["comp"]]
            if cs:
                outp[arm_id] = sum(cs) / len(cs)
        return outp

    SEL, SCO = pins.SELECT_ROLLS, pins.SCORE_ROLLS
    cells = {}
    specs = []
    for c in critics:
        for hz in ("eot", "h2"):
            specs += [(f"{c}/{hz}/k1 vs comp8", lambda r, c=c, hz=hz: pred(r, c, hz, (0,)), lambda r: target(r, ROLLS)),
                      (f"{c}/{hz}/k8 vs comp8", lambda r, c=c, hz=hz: pred(r, c, hz, ROLLS), lambda r: target(r, ROLLS)),
                      (f"{c}/{hz}/k1(r0) vs comp(r1-7)", lambda r, c=c, hz=hz: pred(r, c, hz, (0,)), lambda r: target(r, ROLLS[1:])),
                      (f"{c}/{hz}/sel(0-3) vs comp sco(4-7)", lambda r, c=c, hz=hz: pred(r, c, hz, SEL), lambda r: target(r, SCO))]
    specs += [("comp r0 vs comp(r1-7)  [cost-matched K=1 rollout]", lambda r: target(r, (0,)), lambda r: target(r, ROLLS[1:])),
              ("comp sel(0-3) vs comp sco(4-7)  [label split-half]", lambda r: target(r, SEL), lambda r: target(r, SCO))]
    for name, pf, tf in specs:
        rhos, top1, n, piv_scores, piv_y = [], 0, 0, [], []
        n_lt3 = n_const = 0
        for rec in windows:
            p, y = pf(rec), tf(rec)
            arms = [a for a in p if a in y]
            if len(arms) < 3:
                n_lt3 += 1   # void/crash-thinned window: fewer than 3 scored arms
                continue
            pv, yv = [p[a] for a in arms], [y[a] for a in arms]
            rho = spearman(pv, yv)
            if rho != rho:
                n_const += 1  # a constant side (no-op arms replay natural under CRN)
                continue
            rhos.append(rho)
            n += 1
            top1 += int(max(arms, key=lambda a: p[a]) == max(arms, key=lambda a: y[a]))
            piv_scores.append(max(pv))
            piv_y.append(int(rec["certified_lane"]))
        rhos_s = sorted(rhos)
        cells[name] = {"n_windows": n, "n_lt3_arms": n_lt3, "n_constant": n_const,
                       "spearman_mean": round(sum(rhos) / n, 3) if n else None,
                       "spearman_median": round(rhos_s[n // 2], 3) if n else None,
                       "spearman_se": round((sum((x - sum(rhos) / n) ** 2 for x in rhos) / max(1, n - 1)) ** 0.5 / n ** 0.5, 3) if n > 1 else None,
                       "top1": round(top1 / n, 3) if n else None,
                       "pivotality_auc": round(_auc(piv_scores, piv_y), 3) if n else None}
    headline = cells.get("fullvis/eot/k1 vs comp8", {})
    rho = headline.get("spearman_mean")
    verdict = (None if rho is None else "ADOPT" if rho >= BARS["adopt"]
               else "HYBRID" if rho >= BARS["hybrid"] else "RETIRE")
    res = {"run": str(out), "store": str(store_dir), "n_windows_manifest": len(man["windows"]),
           "n_windows_read": len(windows), "tally": dict(tally), "bars": BARS,
           "headline": {"cell": "fullvis/eot/k1 vs comp8", **headline}, "verdict": verdict,
           "certified_lane_rate": round(sum(w["certified_lane"] for w in windows) / max(1, len(windows)), 3),
           "cells": cells}
    json.dump({**res, "windows": windows}, open(out / "lookahead-read.json", "w"))
    lines = [f"# Critic-lookahead read — {out.name}", "",
             f"windows read {len(windows)} / {len(man['windows'])}; tally {dict(tally)}",
             f"certified (lane's own rolls) {res['certified_lane_rate']}", "",
             f"**Headline: fullvis / eot / K=1 vs 8-roll composite: Spearman {rho} → {verdict}** "
             f"(bars adopt ≥ {BARS['adopt']}, hybrid ≥ {BARS['hybrid']})", "",
             "| cell | n (<3 arms / const) | Spearman mean ± se | median | top-1 | pivotality AUC |",
             "|---|---|---|---|---|---|"]
    for name, cc in cells.items():
        lines.append(f"| {name} | {cc['n_windows']} ({cc['n_lt3_arms']} / {cc['n_constant']}) | "
                     f"{cc['spearman_mean']} ± {cc['spearman_se']} | "
                     f"{cc['spearman_median']} | {cc['top1']} | {cc['pivotality_auc']} |")
    (out / "lookahead-read.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--name", required=True)
    r.add_argument("--n", type=int, default=200)
    r.add_argument("--all", action="store_true")
    r.add_argument("--lanes", type=int, default=8)
    r.add_argument("--heap", default="4g")
    r.add_argument("--port", type=int, default=50077)
    r.add_argument("--dry-run", action="store_true")
    rd = sub.add_parser("read")
    rd.add_argument("--run", required=True)
    rd.add_argument("--store", default=None)
    rd.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if a.cmd == "run":
        run(a)
    else:
        read(a)


if __name__ == "__main__":
    main()
