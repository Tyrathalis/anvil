"""M6 label-expansion campaign: c2 drill-mode tranche for the B-2 lever
(ADR-0044 decision 3, user-approved 2026-08-08).

The B-2 unfreeze probe cleared the frozen-benchmark gate and its label
curve was rising at the 3.6K boundary (1K 0.443 -> 2K 0.450 -> 3.6K
0.4769). This campaign buys the labels the lever is starved of — c2 era
ONLY (labels are policy-conditional; c1 feeds nothing we build).

Standing disciplines wired in:
  - Freeze protocol (label_merge): holdout-hashing games are dropped
    PRE-SPEND (drill_sweep --filter-holdout / plan-time curation filter);
    the final merge proves the frozen holdout unchanged.
  - Curation runs RAW, not isotonic-remapped (population consistency with
    the frozen benchmark — the 437->77 calibrated-curation finding is a
    next-cycle design input, never a mid-experiment switch).
  - Unmodified pinned engine jar (ADR-0025: a crash fix is always a
    dataset boundary — no fork changes mid-era; the measured ~12% crash
    re-launch waste is the price of era consistency).
  - Mid-campaign probe checkpoints (tranche_checkpoint): the curve is
    re-read at each phase boundary; a flat point pauses the campaign
    (exit 2) instead of spending the second day.

Phases (each skipped if its .done marker exists — kill/rerun resumes):
  p1  five untapped offset arms (o1/o3/o5/o6/peak) on the EXISTING fresh
      curation's map (drill-map-r11i019ext-k8) — no generation needed,
      ~1.4-1.7K labels, ~4h.
  ck1 checkpoint -> continue/pause.
  p2  fresh mainlines (2x800 games, new seed base) -> ingest -> traces
      (both critics) -> RAW analyze -> train-only curation filter ->
      map crash:0 + seven offset arms -> ~2.8K labels, ~9h.
  ck2 checkpoint -> continue/pause (informational at the end).
  fin label_merge (freeze-proven) -> full unfreeze re-probe
      (prep + N sweep x 3 seeds on the merged set) -> notify.

Usage:
  uv run python scripts/tranche_c2.py [--smoke] [--workers 16]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from label_merge import held_out  # noqa: E402

from anvil.training.notify import notify  # noqa: E402
from anvil.training.selfplay import RUNS_DIR, _start_server, _stop_server, batch_chunk  # noqa: E402

POLICY = "data/training/d6-run11/iter-019/train/last.pt"
ERA_CRITIC = "data/training/d6-run11/iter-019/critic/last.pt"
D4_CRITIC = "data/training/d4-critic-fullvis/last.pt"
SEED_BASE = 20260808
PORT = 50071
BASE = "data/runs/tranche-c2-20260808"
P1_MAP = "data/runs/drill-map-r11i019ext-k8"        # tranche B's fresh map
P2_MAP = f"{BASE}/p2-map"
TRACE_ERA3 = "data/runs/early-doom-run11-i019-ext3"
TRACE_D43 = "data/runs/early-doom-run11-d4crit-ext3"
MERGED = "data/runs/labelset-c2-v3/dataset.jsonl"
FINAL_PROBE = "data/runs/unfreeze-probe-v2"
P1_ARMS = "o1:crash:-1,o3:crash:-3,o5:crash:-5,o6:crash:-6,peak:peak:0"
P2_ARMS = ("o1:crash:-1,o2:crash:-2,o3:crash:-3,o4:crash:-4,"
           "o5:crash:-5,o6:crash:-6,peak:peak:0")


WATCH_STATE = {"done": False, "phase_start": 0.0, "step": "startup",
               "stalled": False}


def _run(cmd: list[str], ok_codes: tuple[int, ...] = (0,)) -> int:
    print(f"[tranche-c2] $ {' '.join(cmd)}", flush=True)
    WATCH_STATE["phase_start"] = time.time()   # a new step is progress
    WATCH_STATE["step"] = " ".join(cmd[1:4])
    rc = subprocess.run(cmd, cwd=ROOT).returncode
    if rc not in ok_codes:
        raise RuntimeError(f"step failed rc={rc}: {cmd[:4]}...")
    return rc


def _campaign_watchdog(stall_min: int) -> None:
    """Stall alerts across EVERY phase (drill_sweep's watchdog only covers
    its own arms): every 5 min, take the newest mtime over the
    phase-relevant artifact roots; quiet > stall_min while running =>
    notify (re-notify every 4x stall_min while still stalled, re-arm on
    recovery). On any sign of life, touch BASE/heartbeat — the external
    anvil_watchd registration watches BASE, so the heartbeat propagates
    progress from roots outside BASE (generation run dirs, trace dirs)
    and watchd stays a pure dead-man's switch for process death.
    Python glob returns [] on not-yet-existing dirs (the zsh
    unmatched-glob lesson does not bite here)."""
    last_alert = 0.0
    while not WATCH_STATE["done"]:
        time.sleep(300)
        if WATCH_STATE["done"]:
            break
        newest = WATCH_STATE["phase_start"]
        pats = [
            f"{ROOT / BASE}/**",
            f"{ROOT / TRACE_ERA3}/*", f"{ROOT / TRACE_D43}/*",
            str(ROOT / "data/runs" / "c2t3-*" / "**"),
            str(ROOT / "data/runs" / "drill*" / "workers" / "*"
                / "labels.jsonl"),
            str(ROOT / "data/runs" / "drill*" / "workers" / "*" / "*.log"),
        ]
        for pat in pats:
            for p in glob.glob(pat, recursive=True):
                try:
                    newest = max(newest, os.path.getmtime(p))
                except OSError:
                    continue
        quiet_min = (time.time() - newest) / 60
        if quiet_min < stall_min:
            WATCH_STATE["stalled"] = False
            try:
                (ROOT / BASE / "heartbeat").touch()
            except OSError:
                pass
        elif (not WATCH_STATE["stalled"]
              or time.time() - last_alert > 4 * stall_min * 60):
            WATCH_STATE["stalled"] = True
            last_alert = time.time()
            notify("tranche c2 STALLED",
                   f"no artifact progress in {quiet_min:.0f} min at step "
                   f"'{WATCH_STATE['step']}' — process alive but quiet; "
                   "kill + rerun resumes at the current phase")


def _watchd(action: str) -> None:
    """External dead-man's switch: anvil_watchd (10-min systemd timer)
    alarms if this pid dies or BASE (heartbeat included) goes quiet."""
    cmd = [sys.executable, "scripts/anvil_watchd.py", action,
           "--name", "tranche-c2"]
    if action == "register":
        cmd += ["--pid", str(os.getpid()), "--dir", str(ROOT / BASE),
                "--stall-min", "90"]
    subprocess.run(cmd, cwd=ROOT)


def _marker(name: str) -> Path:
    return Path(ROOT / BASE / f"{name}.done")


def _phase_done(name: str) -> bool:
    if _marker(name).exists():
        print(f"[tranche-c2] phase {name} already done — skipping",
              flush=True)
        return True
    return False


def _finish(name: str) -> None:
    _marker(name).parent.mkdir(parents=True, exist_ok=True)
    _marker(name).write_text(f"{time.time()}\n")


def _launch_arm(seat: int, games: int, workers: int) -> Path:
    purpose = f"c2t3-s{seat}"
    before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
    _run([sys.executable, "-m", "anvil.bridge.harness", "launch", "--pool",
          "--games", str(games), "--games-per-pair", "5",
          "--workers", str(workers),
          "--chunk", str(batch_chunk(games, workers, 30)),
          "--bridge", f"grpc:localhost:{PORT}",
          "--obs", "--census", "--reask",
          "--bridge-seats", str(seat),
          "--purpose", purpose, "--seed-base", str(SEED_BASE)])
    new = set(glob.glob(str(RUNS_DIR / f"{purpose}-*"))) - before
    if len(new) != 1:
        raise RuntimeError(f"expected one new run dir for {purpose}: {new}")
    return Path(new.pop())


def _label_dirs() -> list[str]:
    dirs = [f"{BASE}/p1-arms/arm-{t}" for t in
            ("o1", "o3", "o5", "o6", "peak")]
    dirs += [P2_MAP]
    dirs += [f"{BASE}/p2-arms/arm-{t}" for t in
             ("o1", "o2", "o3", "o4", "o5", "o6", "peak")]
    return [d for d in dirs if Path(ROOT / d / "drills.jsonl").exists()]


def _checkpoint(tag: str, pause_ok: bool) -> None:
    cmd = [sys.executable, "scripts/tranche_checkpoint.py",
           "--out", f"{BASE}/{tag}"]
    for d in _label_dirs():
        cmd += ["--labels", d]
    rc = _run(cmd, ok_codes=(0, 2))
    if rc == 2 and not pause_ok:
        notify("tranche c2 PAUSED",
               f"{tag}: curve point flat/regressing — campaign stopped, "
               "everything resumable; user decides")
        raise SystemExit(2)


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--games-per-arm", type=int, default=800)
    ap.add_argument("--smoke", action="store_true",
                    help="p1 limit 6 rows, 16 games/arm in p2, map limit 8")
    a = ap.parse_args()
    games = 16 if a.smoke else a.games_per_arm
    if a.smoke:  # a smoke must never satisfy the real campaign's markers
        g = globals()
        g["BASE"] = BASE + "-smoke"
        g["P2_MAP"] = f"{g['BASE']}/p2-map"
        g["TRACE_ERA3"] = TRACE_ERA3 + "-smoke"
        g["TRACE_D43"] = TRACE_D43 + "-smoke"
        g["MERGED"] = "data/runs/labelset-c2-v3-smoke/dataset.jsonl"
        g["FINAL_PROBE"] = FINAL_PROBE + "-smoke"
    t0 = time.time()
    Path(ROOT / BASE).mkdir(parents=True, exist_ok=True)
    WATCH_STATE["phase_start"] = t0
    ap_stall = 75  # > the ~60-min quiet ceiling of server boot + replay
    threading.Thread(target=_campaign_watchdog, args=(ap_stall,),
                     daemon=True).start()
    if not a.smoke:
        _watchd("register")

    try:
        # ---- p1: untapped offset arms on the existing fresh map ----
        if not _phase_done("p1"):
            _run([sys.executable, "scripts/drill_sweep.py",
                  "--map", P1_MAP,
                  "--bins", "lost,long_shot,coin,winnable",
                  "--arms", P1_ARMS,
                  "--out", f"{BASE}/p1-arms",
                  "--workers", str(a.workers), "--chunk", "17",
                  "--port", str(PORT), "--filter-holdout"]
                 + (["--limit", "6"] if a.smoke else []))
            _finish("p1")
            n = sum(1 for d in _label_dirs() for _ in
                    open(ROOT / d / "drills.jsonl"))
            notify("tranche c2 p1 done",
                   f"{n} labels banked in {(time.time() - t0) / 3600:.1f}h")

        # ---- checkpoint 1 ----
        if not _phase_done("ck1"):
            _checkpoint("ck1", pause_ok=a.smoke)
            _finish("ck1")

        # ---- p2: fresh games -> curation -> map + arms ----
        if not _phase_done("p2-gen"):
            log = Path(ROOT / BASE / "server.log")
            server = _start_server(POLICY, PORT, log, sample=False)
            try:
                run_dirs = [_launch_arm(0, games, a.workers),
                            _launch_arm(1, games, a.workers)]
            finally:
                _stop_server(server)
            for rd in run_dirs:
                _run([sys.executable, "-m", "anvil.store", "ingest", str(rd)])
                store = ROOT / "data" / "trajectories" / rd.name
                if not store.exists():
                    raise RuntimeError(f"ingest did not produce {store}")
            (Path(ROOT / BASE) / "p2-stores.json").write_text(
                json.dumps([rd.name for rd in run_dirs]) + "\n")
            _finish("p2-gen")

        stores = json.loads((Path(ROOT / BASE) / "p2-stores.json").read_text())
        if not _phase_done("p2-trace"):
            arms = [f"data/trajectories/{s}:{i}" for i, s in enumerate(stores)]
            for ckpt, out in ((ERA_CRITIC, TRACE_ERA3), (D4_CRITIC, TRACE_D43)):
                cmd = [sys.executable, "scripts/early_doom.py", "trace",
                       "--ckpt", ckpt, "--out", out]
                for arm in arms:
                    cmd += ["--arm", arm]
                _run(cmd)
            # RAW analyze — curation population-matched to the benchmark
            _run([sys.executable, "scripts/early_doom.py", "analyze",
                  "--out", TRACE_ERA3])
            # train-only curation: the freeze protocol's plan-time filter
            src = Path(ROOT / TRACE_ERA3 / "curation.jsonl")
            dst = Path(ROOT / BASE / "p2-curation-trainonly.jsonl")
            kept = dropped = 0
            with dst.open("w") as f:
                for line in src.open():
                    c = json.loads(line)
                    if held_out(c["store"], c["g"]):
                        dropped += 1
                        continue
                    f.write(line)
                    kept += 1
            print(f"[tranche-c2] p2 curation: {kept} train games "
                  f"({dropped} holdout-hash dropped pre-spend)")
            _finish("p2-trace")

        if not _phase_done("p2-drill"):
            _run([sys.executable, "-m", "anvil.grindstone", "plan",
                  "--curation", f"{BASE}/p2-curation-trainonly.jsonl",
                  "--out", P2_MAP, "--ckpt", POLICY, "--k", "8",
                  "--anchor", "crash", "--turn-offset", "0"]
                 + (["--limit", "8"] if a.smoke else []))
            _run([sys.executable, "-m", "anvil.grindstone", "generate",
                  "--manifest", P2_MAP, "--port", str(PORT),
                  "--workers", str(a.workers), "--chunk", "17",
                  "--drill-stop"])
            _run([sys.executable, "-m", "anvil.grindstone", "report",
                  "--manifest", P2_MAP])
            if not a.smoke:
                _run([sys.executable, "scripts/drill_sweep.py",
                      "--map", P2_MAP,
                      "--bins", "lost,long_shot,coin,winnable",
                      "--arms", P2_ARMS,
                      "--out", f"{BASE}/p2-arms",
                      "--workers", str(a.workers), "--chunk", "17",
                      "--port", str(PORT)])
                # map already train-only => arms inherit; --filter-holdout
                # unnecessary but harmless — belt stays at the merge
            _finish("p2-drill")

        # ---- checkpoint 2 (informational: campaign is done generating) ----
        if not _phase_done("ck2"):
            _checkpoint("ck2", pause_ok=True)
            _finish("ck2")

        # ---- final merge (freeze-proven) + full re-probe ----
        if not _phase_done("merge"):
            cmd = [sys.executable, "scripts/label_merge.py", "merge",
                   "--base", "data/runs/frozen-probe-ext2-c2/dataset.jsonl",
                   "--era", "c2", "--out", MERGED,
                   "--trace-era", "data/runs/early-doom-run11-i019-ext",
                   "--trace-era", TRACE_ERA3,
                   "--trace-d4", "data/runs/early-doom-run11-d4crit-ext",
                   "--trace-d4", TRACE_D43]
            for d in _label_dirs():
                cmd += ["--labels", d]
            _run(cmd)
            _run([sys.executable, "scripts/label_merge.py", "check",
                  "--base", "data/runs/frozen-probe-ext2-c2/dataset.jsonl",
                  "--dataset", MERGED])
            _finish("merge")

        if not _phase_done("probe"):
            _run([sys.executable, "scripts/unfreeze_probe.py", "prep",
                  "--dataset", MERGED, "--out", FINAL_PROBE])
            _run([sys.executable, "scripts/unfreeze_probe.py", "sweep",
                  "--dataset", MERGED, "--out", FINAL_PROBE,
                  "--inner-pool-dataset",
                  "data/runs/frozen-probe-ext2-c2/dataset.jsonl"]
                 + (["--ns", "2", "--lrs", "3e-5", "--seeds", "0",
                     "--max-epochs", "3", "--patience", "2"] if a.smoke
                    else ["--ns", "0,1,2,4", "--lrs", "3e-5",
                          "--seeds", "0,1,2"]))
            _finish("probe")

        wall_h = (time.time() - t0) / 3600
        report = json.loads(
            (ROOT / FINAL_PROBE / "unfreeze-probe-report.json").read_text())
        best = max(report["cells"], key=lambda c: c["holdout_spearman"])
        notify("tranche c2 CAMPAIGN DONE",
               f"merged {MERGED}; best N={best['n_unfreeze']} holdout "
               f"{best['holdout_spearman']} (3.6K point 0.4769) "
               f"in {wall_h:.1f}h")
        print(f"[tranche-c2] DONE in {wall_h:.1f}h")
    except SystemExit:
        raise
    except BaseException as e:
        notify("tranche c2 FAILED", f"{type(e).__name__}: {e}")
        raise
    finally:
        WATCH_STATE["done"] = True
        if not a.smoke:
            _watchd("unregister")


if __name__ == "__main__":
    main()
