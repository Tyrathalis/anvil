#!/usr/bin/env python3
"""anvil.runs — the one launcher for long-running box jobs (ADR-0107).

The launch checklist as code: every detached run goes through
`python -m anvil.runs launch --name N --dir D -- <cmd>` and gets, by
construction, what the checklist used to ask each script to remember:

  detach      double-fork + setsid, stdin from /dev/null, the log in D
  buffering   PYTHONUNBUFFERED=1 in the child's environment
  priority    nice (default 19); --memory-max wraps the child in a
              systemd-run --user scope where systemd is present (Linux),
              ignored with a note elsewhere
  state       runs/<N>.json under the state dir: running -> done | failed
              (exit code, the log tail). A failure is a RECORDED state, never
              an absence — the 09-15 paired read failed in 18 s, unregistered
              cleanly and nobody knew for an hour.
  stall       the supervisor (this process, alive for the run's whole life)
              ticks on the newest mtime under D: running -> stalled ->
              recovered, on transition only
  alerts      every transition appends to alerts.jsonl (id, ts, run, kind,
              msg, acked=false) — the queue the check-in drains (a scheduled
              Claude task, or anyone's poll); plus best-effort sinks:
              $ANVIL_NOTIFY_CMD <title> <msg>, then a desk toast
              (notify-send / osascript) — the desk is a side effect, never
              the coverage
  coverage    the launcher prints ONE line naming the state file, the stall
              threshold and the sinks armed — the launch message's coverage
              list is that line

No registry, no timer, no per-run waiter: one supervisor per run is its own
watchdog. Stdlib only, zero repo imports — it must keep working while the
tree is mid-run-frozen or broken (the watchd rule). Portable: Linux / macOS
(no systemd, no /proc needed).

Verbs:
  launch  --name N --dir D [--stall-min 60] [--nice 19] [--memory-max 20G]
          [--log D/run.log] [--tick-sec 120] -- cmd...
  status  [--json]                 every run's state (newest first)
  wait    --name N [--timeout S]   block until the run is done | failed
  alerts  [--unacked] [--json]     the queue
  ack     --all | --id ID...       mark alerts read
  prune   [--days 30]              drop terminal run records older than N days
State dir: $ANVIL_STATE_DIR, else ~/.local/state/anvil.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


def state_dir() -> Path:
    d = Path(os.environ.get("ANVIL_STATE_DIR") or Path.home() / ".local" / "state" / "anvil")
    (d / "runs").mkdir(parents=True, exist_ok=True)
    return d


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _run_file(name: str) -> Path:
    return state_dir() / "runs" / f"{name}.json"


def _write_json(p: Path, obj: dict) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1))
    os.replace(tmp, p)


def read_run(name: str) -> dict | None:
    p = _run_file(name)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------- alerts


def alert(run: str, kind: str, msg: str, run_dir: str | None = None, tag: str = "anvil") -> dict:
    """Append one alert to the queue and fan out to the best-effort sinks.
    Never raises: no notification path may kill the job it reports on."""
    rec = {
        "id": uuid.uuid4().hex[:12],
        "ts": _now(),
        "run": run,
        "kind": kind,
        "msg": msg,
        "dir": run_dir,
        "acked": False,
    }
    try:
        with open(state_dir() / "alerts.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception as e:  # noqa: BLE001
        print(f"[runs] alert queue write failed: {e}", file=sys.stderr, flush=True)
    title = f"{tag} {run} {kind.upper()}"
    print(f"[runs] {title}: {msg}", flush=True)
    if os.environ.get("ANVIL_NOTIFY_SILENT"):
        return rec
    cmd = os.environ.get("ANVIL_NOTIFY_CMD")
    if cmd:
        try:
            subprocess.run([cmd, title, msg], timeout=30, check=False)
        except Exception as e:  # noqa: BLE001
            print(f"[runs] ANVIL_NOTIFY_CMD failed: {e}", file=sys.stderr, flush=True)
    try:
        if shutil.which("notify-send"):
            subprocess.run(["notify-send", "-u", "critical", title, msg], timeout=10, check=False)
        elif shutil.which("osascript"):
            script = f'display notification "{msg[:200]}" with title "{title}"'.replace("\\", "")
            subprocess.run(["osascript", "-e", script], timeout=10, check=False)
    except Exception:  # noqa: BLE001
        pass
    return rec


def read_alerts(unacked_only: bool = False) -> list[dict]:
    p = state_dir() / "alerts.jsonl"
    if not p.exists():
        return []
    out = []
    for ln in p.read_text().splitlines():
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if unacked_only and r.get("acked"):
            continue
        out.append(r)
    return out


def ack_alerts(ids: set[str] | None) -> int:
    """ids None = all. Returns the number acked."""
    p = state_dir() / "alerts.jsonl"
    if not p.exists():
        return 0
    rows, n = [], 0
    for ln in p.read_text().splitlines():
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not r.get("acked") and (ids is None or r.get("id") in ids):
            r["acked"] = True
            r["acked_ts"] = _now()
            n += 1
        rows.append(r)
    tmp = p.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r) + "\n" for r in rows))
    os.replace(tmp, p)
    return n


# ------------------------------------------------------------- supervisor


def newest_mtime(root: Path) -> float:
    """Newest file mtime under root (the run's own artifact dir, not a
    project-wide tree); 0 when nothing is there yet."""
    newest = 0.0
    try:
        for dirpath, _dirs, files in os.walk(root):
            for fn in files:
                try:
                    m = os.stat(os.path.join(dirpath, fn)).st_mtime
                except OSError:
                    continue
                if m > newest:
                    newest = m
    except OSError:
        pass
    return newest


def _tail(path: Path, lines: int = 15, width: int = 200) -> str:
    try:
        data = path.read_bytes()[-32768:].decode("utf-8", "replace")
    except OSError:
        return ""
    return "\n".join(ln[:width] for ln in data.splitlines()[-lines:])


def _child_cmd(cmd: list[str], nice: int, memory_max: str | None, name: str) -> tuple[list[str], str | None]:
    """The command the supervisor spawns; a note when a requested wrapper
    is unavailable on this platform."""
    note = None
    if memory_max:
        if shutil.which("systemd-run") and sys.platform.startswith("linux"):
            return (
                ["systemd-run", "--user", "--scope", "--quiet", f"--unit=anvil-{name}-{os.getpid()}",
                 "-p", f"MemoryMax={memory_max}", "-p", f"Nice={nice}"] + cmd,
                None,
            )
        note = f"--memory-max {memory_max} ignored: no systemd-run on this platform"
    return cmd, note


def supervise(a: argparse.Namespace, cmd: list[str]) -> int:
    """Runs in the detached grandchild: spawn the command, tick the stall
    check, write the terminal state, alert on every transition."""
    run_dir = Path(a.dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    log = Path(a.log).resolve() if a.log else run_dir / "run.log"
    env = dict(os.environ, PYTHONUNBUFFERED="1", ANVIL_RUN_NAME=a.name)
    real_cmd, note = _child_cmd(cmd, a.nice, a.memory_max, a.name)
    stall_s = a.stall_sec if a.stall_sec is not None else a.stall_min * 60
    logf = open(log, "ab")
    logf.write(f"[runs] {_now()} launch {a.name}: {' '.join(cmd)}\n".encode())
    if note:
        logf.write(f"[runs] {note}\n".encode())
    logf.flush()

    def preexec() -> None:
        try:
            os.nice(a.nice)
        except OSError:
            pass

    try:
        child = subprocess.Popen(
            real_cmd, stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            env=env, cwd=a.cwd or None, preexec_fn=preexec if not a.memory_max else None,
        )
    except Exception as e:  # noqa: BLE001
        st = {
            "name": a.name, "state": "failed", "rc": -1, "started": _now(), "ended": _now(),
            "cmd": cmd, "dir": str(run_dir), "log": str(log), "error": f"spawn failed: {e}",
            "supervisor_pid": os.getpid(),
        }
        _write_json(_run_file(a.name), st)
        alert(a.name, "failed", f"spawn failed: {e}", str(run_dir), a.tag)
        return 1
    st = {
        "name": a.name, "state": "running", "pid": child.pid, "supervisor_pid": os.getpid(),
        "started": _now(), "cmd": cmd, "dir": str(run_dir), "log": str(log),
        "stall_sec": stall_s, "tick_sec": a.tick_sec, "note": note,
    }
    _write_json(_run_file(a.name), st)

    def forward(signum, _frame):  # noqa: ANN001
        try:
            os.killpg(os.getpgid(child.pid), signum)
        except Exception:  # noqa: BLE001
            child.send_signal(signum)

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)

    stalled = False
    t0 = time.time()
    last_tick = t0
    rc = None
    while True:
        rc = child.poll()
        if rc is not None:
            break
        time.sleep(min(5.0, a.tick_sec))
        if time.time() - last_tick < a.tick_sec:
            continue
        last_tick = time.time()
        newest = max(newest_mtime(run_dir), t0)
        age = time.time() - newest
        if not stalled and age > stall_s:
            stalled = True
            st.update(state="stalled", stalled_since=_now())
            _write_json(_run_file(a.name), st)
            alert(a.name, "stalled", f"no artifact under {run_dir} for {int(age // 60)} min", str(run_dir), a.tag)
        elif stalled and age <= stall_s:
            stalled = False
            st.update(state="running")
            st.pop("stalled_since", None)
            _write_json(_run_file(a.name), st)
            alert(a.name, "recovered", "fresh artifacts again", str(run_dir), a.tag)
    logf.write(f"[runs] {_now()} exit rc={rc}\n".encode())
    logf.close()
    kind = "done" if rc == 0 else "failed"
    st.update(state=kind, rc=rc, ended=_now(), wall_s=int(time.time() - t0))
    st.pop("stalled_since", None)
    _write_json(_run_file(a.name), st)
    tail = _tail(log)
    msg = f"rc={rc} after {st['wall_s']} s; log {log}" + ("" if rc == 0 else f"\n{tail}")
    alert(a.name, kind, msg, str(run_dir), a.tag)
    return 0 if rc == 0 else 1


def launch(a: argparse.Namespace, cmd: list[str]) -> int:
    if not cmd:
        print("launch: no command after --", file=sys.stderr)
        return 2
    prev = read_run(a.name)
    if prev and prev.get("state") in ("running", "stalled") and _alive(prev.get("supervisor_pid")):
        print(f"launch: run {a.name} is still {prev['state']} (supervisor pid {prev['supervisor_pid']})",
              file=sys.stderr)
        return 3
    run_dir = Path(a.dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    if a.foreground:
        return supervise(a, cmd)
    # double fork: the supervisor outlives the launching shell / app
    pid = os.fork()
    if pid == 0:
        os.setsid()
        if os.fork() != 0:
            os._exit(0)
        devnull = os.open(os.devnull, os.O_RDWR)
        os.dup2(devnull, 0)
        sup_log = open(run_dir / "supervisor.log", "ab")
        os.dup2(sup_log.fileno(), 1)
        os.dup2(sup_log.fileno(), 2)
        code = 1
        try:
            code = supervise(a, cmd)
        finally:
            os._exit(code)
    os.waitpid(pid, 0)
    for _ in range(100):
        st = read_run(a.name)
        if st and st.get("started") and (prev is None or st.get("started") != prev.get("started")):
            break
        time.sleep(0.05)
    st = read_run(a.name) or {}
    sinks = ["queue"]
    if os.environ.get("ANVIL_NOTIFY_CMD"):
        sinks.append("notify-cmd")
    if shutil.which("notify-send") or shutil.which("osascript"):
        sinks.append("desk")
    stall_s = a.stall_sec if a.stall_sec is not None else a.stall_min * 60
    print(
        f"[runs] LAUNCHED {a.name}: state {_run_file(a.name)} ({st.get('state', '?')}, pid {st.get('pid')}), "
        f"log {st.get('log')}, stall alarm {stall_s // 60} min on {run_dir}, sinks {'+'.join(sinks)}"
        + (f"; note: {st['note']}" if st.get("note") else ""),
        flush=True,
    )
    return 0 if st.get("state") in ("running", "done") else 1


def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


# ------------------------------------------------------------------ verbs


def status(a: argparse.Namespace) -> int:
    runs = []
    for p in sorted((state_dir() / "runs").glob("*.json"), key=lambda q: q.stat().st_mtime, reverse=True):
        try:
            r = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if r.get("state") in ("running", "stalled") and not _alive(r.get("supervisor_pid")):
            r["state"] = "gone"  # the supervisor died (reboot, kill): not a clean exit
        runs.append(r)
    if a.json:
        print(json.dumps(runs, indent=1))
        return 0
    if not runs:
        print("no runs")
    for r in runs:
        extra = f" rc={r.get('rc')}" if r.get("rc") is not None else ""
        print(f"{r.get('state', '?'):9s} {r['name']:32s} started {r.get('started', '?')}{extra}  dir {r.get('dir')}")
    return 0


def wait(a: argparse.Namespace) -> int:
    t0 = time.time()
    while True:
        r = read_run(a.name)
        if r and r.get("state") in ("done", "failed"):
            print(f"{a.name}: {r['state']} rc={r.get('rc')}")
            return 0 if r["state"] == "done" else 1
        if r and r.get("state") in ("running", "stalled") and not _alive(r.get("supervisor_pid")):
            print(f"{a.name}: gone (supervisor died)")
            return 2
        if a.timeout and time.time() - t0 > a.timeout:
            print(f"{a.name}: wait timeout")
            return 3
        time.sleep(a.poll)


def alerts(a: argparse.Namespace) -> int:
    rows = read_alerts(a.unacked)
    if a.json:
        print(json.dumps(rows, indent=1))
    else:
        for r in rows:
            print(f"{'  ' if r.get('acked') else '! '}{r['ts']} {r['run']} {r['kind'].upper()}: {r['msg'].splitlines()[0][:160]}  [{r['id']}]")
        if not rows:
            print("no alerts" + (" (unacked)" if a.unacked else ""))
    return 0


def ack(a: argparse.Namespace) -> int:
    n = ack_alerts(None if a.all else set(a.id or []))
    print(f"acked {n}")
    return 0


def prune(a: argparse.Namespace) -> int:
    cutoff = time.time() - a.days * 86400
    n = 0
    for p in (state_dir() / "runs").glob("*.json"):
        try:
            r = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if r.get("state") in ("done", "failed") and p.stat().st_mtime < cutoff:
            p.unlink()
            n += 1
    print(f"pruned {n}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd: list[str] = []
    if "--" in argv:
        i = argv.index("--")
        cmd = argv[i + 1:]
        argv = argv[:i]
    ap = argparse.ArgumentParser(prog="anvil.runs", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="verb", required=True)
    la = sub.add_parser("launch")
    la.add_argument("--name", required=True)
    la.add_argument("--dir", required=True, help="the run's artifact dir (stall checks watch it; the log lands in it)")
    la.add_argument("--log", default=None)
    la.add_argument("--cwd", default=None)
    la.add_argument("--stall-min", type=int, default=60)
    la.add_argument("--stall-sec", type=int, default=None, help=argparse.SUPPRESS)
    la.add_argument("--tick-sec", type=float, default=120.0)
    la.add_argument("--nice", type=int, default=19)
    la.add_argument("--memory-max", default=None, help="e.g. 20G: a systemd-run --user scope where available")
    la.add_argument("--tag", default="anvil")
    la.add_argument("--foreground", action="store_true", help="supervise in this process (tests, chains)")
    st = sub.add_parser("status")
    st.add_argument("--json", action="store_true")
    wa = sub.add_parser("wait")
    wa.add_argument("--name", required=True)
    wa.add_argument("--timeout", type=float, default=0)
    wa.add_argument("--poll", type=float, default=10.0)
    al = sub.add_parser("alerts")
    al.add_argument("--unacked", action="store_true")
    al.add_argument("--json", action="store_true")
    ac = sub.add_parser("ack")
    ac.add_argument("--all", action="store_true")
    ac.add_argument("--id", nargs="*")
    pr = sub.add_parser("prune")
    pr.add_argument("--days", type=int, default=30)
    a = ap.parse_args(argv)
    return {"launch": lambda: launch(a, cmd), "status": lambda: status(a), "wait": lambda: wait(a),
            "alerts": lambda: alerts(a), "ack": lambda: ack(a), "prune": lambda: prune(a)}[a.verb]()


if __name__ == "__main__":
    sys.exit(main())
