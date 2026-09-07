"""2,000-game Ante-corrected winrate read (the run-3/run-5 closeout
protocol, formalized): per seat assignment, 1,000 games (200 pairs x 5)
against the heuristic at argmax serve under -reask, then ingest + Ante
certify (full-vis critic) per run, then arms_report --ante.

Usage:
  uv run python scripts/final_read.py \
      --ckpt data/training/d6-run6/iter-019/train/last.pt \
      --name run6-final --port 50065
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

from anvil.training.notify import notify, watch_register, watch_unregister
from anvil.training.selfplay import RUNS_DIR, _run, _start_server, _stop_server

CRITIC = "data/training/d4-critic-fullvis/last.pt"
TRAJ_DIR = Path("data/trajectories")


def main() -> None:
    # Detached stdout to a redirected log is BLOCK-buffered, so a log-tail
    # watcher sees nothing until exit (run-8 held 36h of narration in memory).
    # The driver fixed this for itself on 2026-07-25; reads never got it.
    sys.stdout.reconfigure(line_buffering=True)

    ap = argparse.ArgumentParser(description="2,000-game corrected read")
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--name", required=True, help="report prefix, e.g. run6-final")
    ap.add_argument("--games", type=int, default=1000, help="games per seat arm")
    ap.add_argument("--games-per-pair", type=int, default=5)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--chunk", type=int, default=50)
    ap.add_argument("--port", type=int, default=50065)
    ap.add_argument("--pairs-file", default="data/runs/d5arm-d0-s0-20260714-143546/pairs.txt")
    ap.add_argument("--seed-base", type=int, default=20260710)
    ap.add_argument("--critic", default=CRITIC)
    ap.add_argument(
        "--pool-version",
        default=None,
        help="pool manifest version to stamp on the runs. Default "
        "resolves the same manifest the harness would use "
        "(the data/pool/CURRENT pin since 2026-08-03; the "
        "old mtime-selection hazard is retired) — ingest "
        "warns 'provenance is incomplete' without it.",
    )
    ap.add_argument(
        "--forge-args",
        default=None,
        help="M12 Build 2: extra AnvilRun flags for every worker (the search "
        "directive as the behavior policy, e.g. '-search -searchrate 1 "
        "-searchact 0.05 -searchtemp 0.025'); recorded in each arm's run.json",
    )
    ap.add_argument(
        "--labels", action="store_true", help="per-worker labels.jsonl (the ev:search rows)"
    )
    ap.add_argument("--jar", default=None, help="run this jar (a snapshot copy) instead of target/'s newest")
    ap.add_argument(
        "--heuristic-control",
        action="store_true",
        help="M12 Build 2 control arms (ADR-0104 item 5): NO seat bridged (the "
        "heuristic mirror; --bridge-seats 2) and '-searchseats <seat>' appended "
        "to the forge args per seat run, so the searched heuristic seat sits "
        "where the bridged seat sits in the network arms; the server still "
        "serves the leaf values",
    )
    ap.add_argument(
        "--skip-ante",
        action="store_true",
        help="generation + arms report only (no ingest / Ante certify) — the "
        "day-zero paired diffs need the raw arms, not the corrected number",
    )
    a = ap.parse_args()
    # Self-registration with the standing watcher: the read reports its OWN
    # pid (the 07-31 chain waiter grabbed a pgrep'd pid that was its own
    # wrapper shell and waited on itself forever). Crash without unregister
    # -> the watcher fires GONE.
    watch_register(f"{a.name}-read", RUNS_DIR, stall_min=45)

    if a.pool_version is None:
        from anvil.bridge.harness.pairs import latest_pool_manifest

        a.pool_version = latest_pool_manifest()["pool_version"]
    print(f"[final_read] pool version {a.pool_version}")

    # ---- generation: both seat assignments under one argmax server ----
    arm_dirs: list[Path] = []
    server = _start_server(a.ckpt, a.port, RUNS_DIR / f"{a.name}-arm-server.log", sample=False)
    try:
        for seat in (0, 1):
            purpose = f"{a.name}arm-s{seat}"
            before = set(glob.glob(str(RUNS_DIR / f"{purpose}-*")))
            _run(
                [
                    sys.executable,
                    "-m",
                    "anvil.bridge.harness",
                    "launch",
                    "--pairs-file",
                    a.pairs_file,
                    "--games",
                    str(a.games),
                    "--games-per-pair",
                    str(a.games_per_pair),
                    "--workers",
                    str(a.workers),
                    "--chunk",
                    str(a.chunk),
                    "--bridge",
                    f"grpc:localhost:{a.port}",
                    "--census",
                    "--obs",
                    "--purpose",
                    purpose,
                    "--seed-base",
                    str(a.seed_base),
                    "--pool-version",
                    a.pool_version,
                    "--bridge-seats",
                    "2" if a.heuristic_control else str(seat),
                    "--reask",
                    *(
                        ["--forge-args", f"{a.forge_args or ''} -searchseats {seat}".strip()]
                        if a.heuristic_control
                        else (["--forge-args", a.forge_args] if a.forge_args else [])
                    ),
                    *(["--labels"] if a.labels else []),
                    *(["--jar", a.jar] if a.jar else []),
                ]
            )
            new = set(glob.glob(str(RUNS_DIR / f"{purpose}-*"))) - before
            if len(new) != 1:
                raise RuntimeError(f"expected one new run dir, got {new}")
            arm_dirs.append(Path(new.pop()))
    finally:
        _stop_server(server)

    # ---- ingest + certify per run (certify needs a trajectory store) ----
    ante_reports: list[str] = []
    for rd in ([] if a.skip_ante else arm_dirs):
        _run([sys.executable, "-m", "anvil.store", "ingest", str(rd)])
        store = TRAJ_DIR / rd.name
        if not store.exists():
            raise RuntimeError(f"ingest did not produce {store}")
        rep = RUNS_DIR / f"ante-{rd.name}.json"
        _run(
            [
                sys.executable,
                "-m",
                "anvil.ante.certify",
                "--store",
                str(store),
                "--ckpt",
                a.critic,
                "--out",
                str(rep),
                "--ledger-out",
                f"{rep}.ledger.jsonl",
            ]
        )
        ante_reports.append(str(rep))

    # ---- pooled report ----
    out = RUNS_DIR / f"{a.name}-arms-report.json"
    _run(
        [
            sys.executable,
            "scripts/arms_report.py",
            "--arm",
            f"{a.name}={','.join(map(str, arm_dirs))}",
            *(["--ante", f"{a.name}={','.join(ante_reports)}"] if ante_reports else []),
            "--out",
            str(out),
        ]
    )
    print(f"[final_read] report: {out}")
    # ---- standing analysis battery (run-analysis-protocol.md): eval read —
    # seed-half consistency, distributions, deck spread. Diagnostic only;
    # anomaly lines ride the notify so the report gets read by default ----
    from anvil.evals import battery

    an = (
        battery.emit(
            battery.eval_read,
            a.name,
            [str(d) for d in arm_dirs],
            str(out),
            RUNS_DIR / f"{a.name}-analysis",
        )
        or []
    )
    an_txt = "; ".join(an) if an else "none"
    notify(
        f"anvil {a.name}: read complete",
        f"{out}; battery anomalies: {an_txt}",
        tag="final_read",
    )
    watch_unregister(f"{a.name}-read")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        # argparse --help and clean sys.exit(0) raise SystemExit too; only a
        # NONZERO code is a failure. The first version caught BaseException
        # flat and pushed "read FAILED SystemExit: 0" from a --help call.
        if e.code not in (0, None):
            notify("anvil read FAILED", f"exit {e.code}", tag="final_read")
        raise
    except BaseException as e:  # noqa: BLE001 — a job that dies must SAY so
        notify("anvil read FAILED", f"{type(e).__name__}: {e}", tag="final_read")
        raise
