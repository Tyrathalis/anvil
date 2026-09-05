#!/usr/bin/env python3
"""Label TEST-RETEST for the inline certifier (2026-09-05 diagnostic): re-roll
a sample of harvested windows with FRESH rollout seeds and ask whether the
same adjudication comes back — the noise ceiling any label-learning head can
reach. Also a free replay-parity check: rolls 0-7 re-run under the same
rollSeed identity and must reproduce the originals bit-for-bit.

Mechanics: the harvest games replay through the standard -forceschedule lane
(the mainline's sampled serving is keyed on (game seed, dec id) — the
paired-read/mint replay contract), arms = the window's own sched_arms row,
-rollout 16: rolls 0-7 are the originals (parity), rolls 8-15 are fresh
(retest: SELECT 8-11 / SCORE 12-15, the pinned split shifted by 8).

Usage:
  uv run python scripts/sched_label_retest.py run --name rt1 [--n-cert 40 --n-nat 20 --lanes 8]
  uv run python scripts/sched_label_retest.py read --run data/runs/sched-retest-rt1
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
from schedule_read import arm_scores, load_rows  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data/runs/sched-harvest-h1/harvest-manifest.json"
K_RETEST = 16
CKPT_MAIN = "data/training/d6-run11/iter-019/train/last.pt"


def _sample(args) -> list[dict]:
    m = json.loads(MANIFEST.read_text())
    rows = []
    for b in m["batches"]:
        for ln in list(open(b["labels"]))[1:]:
            r = json.loads(ln)
            r["_run"] = b["run"]
            rows.append(r)
    rng = random.Random(20260905)
    cert = [r for r in rows if r["src"] == "certified"]
    nat = [r for r in rows if r["src"] == "natural"]
    pick = rng.sample(cert, min(args.n_cert, len(cert))) + rng.sample(nat, min(args.n_nat, len(nat)))
    return pick


def run(args) -> None:
    out = REPO / "data/runs" / f"sched-retest-{args.name}"
    out.mkdir(parents=True, exist_ok=True)
    pick = _sample(args)
    by_run: dict[str, list[dict]] = defaultdict(list)
    for r in pick:
        by_run[r["_run"]].append(r)
    jar = sorted((REPO.parent / "forge/forge-gui-desktop/target").glob("*-jar-with-dependencies.jar"),
                 key=lambda p: p.stat().st_mtime)[-1]
    gui = jar.parent.parent.parent / "forge-gui"
    lanes = []
    manifest = {"name": args.name, "created": time.strftime("%Y%m%d-%H%M%S"), "jar": str(jar),
                "jar_sha256": hashlib.sha256(jar.read_bytes()).hexdigest(), "k": K_RETEST,
                "windows": [], "runs": {}}
    for run_dir, rs in by_run.items():
        rd = Path(run_dir)
        rj = json.loads((rd / "run.json").read_text())
        arms = load_arms([str(rd / "workers" / "inv-*" / "labels.jsonl")])
        lines = []
        for r in rs:
            key = (r["g"], r["t"])
            ent = arms.get(key)
            if ent is None:
                continue
            base = f"{r['g']}\t{r['t']}\t{ent['horizon']}\t{ent['seat']}"
            for arm_id, (mode, labels) in sorted(ent["arms"].items()):
                tail = ("\t" + "\t".join(labels)) if labels else ""
                lines.append(f"{base}\t{arm_id}\t{mode}{tail}")
            manifest["windows"].append({"run": run_dir, "g": r["g"], "t": r["t"], "seat": ent["seat"],
                                        "src": r["src"], "orig_arm": r["arm"], "s": r["s"]})
        n_lanes = max(1, round(args.lanes * len(rs) / len(pick)))
        games = sorted({int(ln.split("\t", 1)[0]) for ln in lines})
        lane_of = {g: i % n_lanes for i, g in enumerate(games)}
        tag = rd.name.split("-")[3]  # bNN
        manifest["runs"][run_dir] = {"windows": len(rs), "lanes": n_lanes, "range": [rj["start_index"], rj["games"]]}
        for i in range(n_lanes):
            tsv = out / f"lane-{tag}-{i}.tsv"
            with open(tsv, "w") as f:
                for ln in lines:
                    if lane_of[int(ln.split("\t", 1)[0])] == i:
                        f.write(ln + "\n")
            scratch = out / f"lane-{tag}-{i}.scratch"
            sh = out / f"lane-{tag}-{i}.sh"
            # the harvest run's own replay parameters (run.json), the generation
            # flag set (-reask on, no -paytelemetry), -forceschedule skips
            # unlisted indices without creating a game
            sh.write_text(
                "#!/bin/sh\nset -e\n"
                f"cd '{gui}'\n"
                f"nice -n 19 java -Xms{args.heap} -Xmx{args.heap} -XX:ActiveProcessorCount=2 "
                f"-XX:+ExitOnOutOfMemoryError -jar '{jar}' anvil "
                f"-pairs '{rd / rj['pairs_file']}' -gpp {rj['games_per_pair']} -f Commander "
                f"-range {rj['start_index']} {rj['games']} -seedbase {rj['seed_base']} "
                f"-b grpc:localhost:{args.port} "
                f"-obs '{scratch}.obs.zst' -census '{scratch}.census.jsonl' "
                f"{'-reask ' if rj.get('reask') else ''}"
                f"-rollout {K_RETEST} -labels '{out}/lane-{tag}-{i}.out.jsonl' "
                f"-forceschedule '{tsv}'\n")
            sh.chmod(0o755)
            lanes.append(sh)
    json.dump(manifest, open(out / "retest-manifest.json", "w"), indent=2)
    print(f"[retest] {len(manifest['windows'])} windows over {len(lanes)} lanes -> {out}")
    # server: the harvest's serving config (sampled, fork-instrument)
    scmd = [sys.executable, "-m", "anvil.bridge.server", "--mode", "model", "--ckpt", CKPT_MAIN,
            "--port", str(args.port), "--pass-delta", "0", "--sample", "--temperature", "1.0",
            "--mu-out", str(out / "serve-mu.jsonl"), "--fork-instrument",
            "--counts-out", str(out / "server.counts.json")]
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
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
    fails = [sh.name for sh, p in zip(lanes, procs) if p.wait() != 0]
    if server.poll() is None:
        server.send_signal(signal.SIGTERM)
        try:
            server.wait(timeout=60)
        except subprocess.TimeoutExpired:
            server.kill()
    manifest["lane_failures"] = fails
    manifest["wall_s"] = round(time.monotonic() - t0)
    json.dump(manifest, open(out / "retest-manifest.json", "w"), indent=2)
    print(f"[retest] lanes done in {(time.monotonic() - t0) / 60:.1f} min, failures {fails}")
    read(argparse.Namespace(run=str(out)))


def _certify(entry: dict, seat: int, sel: tuple, sco: tuple) -> dict:
    cands = []
    for arm_id, rows in sorted(entry["arms"].items()):
        if any(r.get("void") for r in rows.values()):
            continue
        s = arm_scores(rows, entry["nat"], seat, sel)
        c = arm_scores(rows, entry["nat"], seat, sco)
        if len(s) < pins.MIN_VALID_ROLLS or len(c) < pins.MIN_VALID_ROLLS:
            continue
        cands.append((sum(s) / len(s), -arm_id, arm_id, c))
    if not cands:
        return {"read": False}
    cands.sort(reverse=True)
    _, _, arm_id, c = cands[0]
    mean = sum(c) / len(c)
    agree = sum(1 for x in c if (x > 0) == (mean > 0)) / len(c)
    return {"read": True, "arm": arm_id, "score_mean": round(mean, 3),
            "certified": mean >= pins.THETA and agree >= pins.CONSISTENT}


def read(args) -> dict:
    out = Path(args.run)
    man = json.loads((out / "retest-manifest.json").read_text())
    new = load_rows([str(out / "lane-*.out.jsonl")])
    tally: Counter = Counter()
    parity: Counter = Counter()
    per = []
    for w in man["windows"]:
        key = (w["g"], w["t"])
        entry = new.get(key)
        if entry is None or entry["skips"]:
            tally["missing_or_skipped"] += 1
            continue
        # parity: rolls 0-7 vs the original completion rows
        orig = load_rows([str(Path(w["run"]) / "workers" / "inv-*" / "labels.jsonl")]).get(key)
        if orig:
            for arm_id, rows in list(entry["arms"].items()) + [(0, entry["nat"])]:
                o_rows = orig["nat"] if arm_id == 0 else orig["arms"].get(arm_id, {})
                for roll in range(pins.K_ROLLS):
                    a, b = rows.get(roll), o_rows.get(roll)
                    if a is None or b is None:
                        parity["missing"] += 1
                    elif (a.get("winner"), a.get("t_end"), a.get("snap")) == (b.get("winner"), b.get("t_end"), b.get("snap")):
                        parity["identical"] += 1
                    else:
                        parity["different"] += 1
        # retest on fresh rolls
        rt = _certify(entry, w["seat"], (8, 9, 10, 11), (12, 13, 14, 15))
        orig_dec = _certify(entry, w["seat"], pins.SELECT_ROLLS, pins.SCORE_ROLLS)  # re-derived from rolls 0-7
        rec = {**w, "orig_rederived": orig_dec, "retest": rt}
        per.append(rec)
        if not rt["read"]:
            tally[f"{w['src']}->unread"] += 1
            continue
        if w["src"] == "certified":
            if rt["certified"] and rt["arm"] == w["orig_arm"]:
                tally["certified->same arm certified"] += 1
            elif rt["certified"]:
                tally["certified->other arm certified"] += 1
            else:
                tally["certified->not certified"] += 1
        else:
            tally["natural->certified" if rt["certified"] else "natural->natural"] += 1
    res = {"tally": dict(tally), "parity_rolls_0_7": dict(parity), "n": len(man["windows"])}
    json.dump({**res, "windows": per}, open(out / "retest-read.json", "w"), indent=2)
    print("[retest] parity (rolls 0-7 vs originals):", dict(parity))
    print("[retest] test-retest:", dict(tally))
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run")
    r.add_argument("--name", required=True)
    r.add_argument("--n-cert", type=int, default=40)
    r.add_argument("--n-nat", type=int, default=20)
    r.add_argument("--lanes", type=int, default=8)
    r.add_argument("--heap", default="3g")
    r.add_argument("--port", type=int, default=50081)
    r.set_defaults(fn=run)
    d = sp.add_parser("read")
    d.add_argument("--run", required=True)
    d.set_defaults(fn=read)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
