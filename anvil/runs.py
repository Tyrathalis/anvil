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
  check-in    (ADR-0107 addendum 09-18) the supervisor itself invokes a
              headless Claude Code session (`claude -p`, read-only tools) on
              the events that need a human: failed, stalled, gone, and done
              after > 1 h — it pushes to the phone, messages the supervising
              desktop session, acks the alert. Event-driven: no polling task
              to remember to enable. `--checkin auto|claude|none` (auto =
              claude when the CLI is on PATH; $ANVIL_CHECKIN overrides); the
              launch runs a self-test so a missing consumer (no CLI, an
              expired login) shows in the coverage line, not the next morning
  watch       --watch <glob> (repeatable) adds artifact roots to the stall
              tick beside --dir: a read chain launched from its own dir writes
              its arms under data/runs/<name>-* and raised two false stalls
              on 09-17 — name those roots and the tick sees them
  pause       `anvil.runs pause --name N [--now] [--wait]` (09-21): STOP in every
              root the command watches + `pause_requested` on the state; the
              supervisor records PAUSED at exit (no FAILED push, no check-in).
  relaunch    `anvil.runs relaunch --name N`: the recorded command again, in
              place (STOP files removed); `--resume-on-gone` at launch lets
              the sweep do this itself after a reboot, capped by --resume-max.
  sweep       `anvil.runs sweep` marks runs whose supervisor died (reboot,
              OOM, kill -9) as gone, alerts, checks in; `install-sweep` puts
              it on a systemd user timer (10 min) where systemd exists

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
  sweep                            mark gone runs (dead supervisor), alert, check in
  install-sweep                    a systemd user timer for sweep (Linux); a cron line elsewhere
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
import threading
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


_HEARTBEAT_LAST = [0.0]


def heartbeat(note: str, every_s: float = 60.0) -> bool:
    """A paused-but-alive signal for the stall tick (09-21): a job that is
    deliberately idle (the harness yielding the GPU, the learner parked on a
    VRAM cotenant) writes <run dir>/heartbeat.json so the supervisor sees a
    fresh artifact instead of raising the false-stall class (the 09-17 chain
    raised two during a real 3 h yield). Resolved through $ANVIL_RUN_NAME
    (the supervisor exports it); a no-op outside a launched run. Throttled."""
    name = os.environ.get("ANVIL_RUN_NAME")
    if not name or time.time() - _HEARTBEAT_LAST[0] < every_s:
        return False
    st = read_run(name)
    if not st or not st.get("dir"):
        return False
    try:
        _write_json(Path(st["dir"]) / "heartbeat.json", {"ts": _now(), "note": note})
    except OSError:
        return False
    _HEARTBEAT_LAST[0] = time.time()
    return True


def alert(run: str, kind: str, msg: str, run_dir: str | None = None, tag: str = "anvil",
          sinks: bool = True) -> dict:
    """Append one alert to the queue and fan out to the best-effort sinks.
    Never raises: no notification path may kill the job it reports on.
    sinks=False = the queue only (the check-in's own record)."""
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
    if os.environ.get("ANVIL_NOTIFY_SILENT") or not sinks:
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
        if os.path.isfile(root):  # a --watch glob may name files
            return os.stat(root).st_mtime
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


# ------------------------------------------------------------ the LLM check-in

CHECKIN_TOOLS = ("ToolSearch,ListAgents,SendMessage,PushNotification,Read,"
                 "Bash(uv run python -m anvil.runs ack:*),Bash(python -m anvil.runs ack:*),Bash(tail:*)")
CHECKIN_MIN_GAP_S = 20 * 60   # a flapping stall raises at most one check-in per 20 min
CHECKIN_DONE_MIN_S = 3600     # a done under an hour is not worth a phone push
CHECKIN_TIMEOUT_S = 600


def checkin_mode(requested: str | None) -> str:
    """auto -> claude when the CLI is on PATH, else none; $ANVIL_CHECKIN overrides."""
    m = os.environ.get("ANVIL_CHECKIN") or requested or "auto"
    if m == "auto":
        return "claude" if shutil.which("claude") else "none"
    return m


def checkin_prompt(rec: dict, st: dict, tail: str) -> str:
    run, kind = rec["run"], rec["kind"].upper()
    first = (rec.get("msg") or "").splitlines()[0][:200] if rec.get("msg") else ""
    return (
        "You are the Anvil run check-in (ADR-0107). You are read-only: never edit files, never kill, launch "
        "or fix anything — diagnosis belongs to the supervising session.\n"
        f"Event: run \"{run}\" is {kind}: {first}\n"
        f"State file: {_run_file(run)}\nLog: {st.get('log')}\nRun dir: {st.get('dir')}\n"
        f"Started: {st.get('started')}  Alert id: {rec['id']}\n"
        f"Last log lines:\n{tail}\n\n"
        "Do exactly this:\n"
        "1. If PushNotification, SendMessage or ListAgents are deferred in your tool list, load them with "
        "ToolSearch (query \"select:PushNotification,SendMessage,ListAgents\").\n"
        "2. Send ONE push notification with PushNotification, under 200 characters, leading with what to act on, "
        f"e.g. \"{run} {kind}: <the first error line / the minutes stalled / the hours run>\".\n"
        "3. Call ListAgents. With SendMessage, send one message to every peer session on this machine marked "
        "interactive whose name or title contains \"anvil\" (case-insensitive); if there is none, to the most "
        "recently started interactive session. The message: the event kind, the run name, the state file, the "
        "log path and the error lines. Do not ask them questions.\n"
        f"4. Ack this alert with one shell command: `uv run python -m anvil.runs ack --id {rec['id']}` "
        f"(if uv is missing: `python -m anvil.runs ack --id {rec['id']}`).\n"
        "5. Reply with ONE line: what you pushed and which sessions you messaged. Nothing else."
    )


def llm_checkin(rec: dict, st: dict, timeout: int = CHECKIN_TIMEOUT_S) -> dict:
    """Invoke a headless Claude Code session on one alert. Never raises; the
    outcome lands in the queue as a `checkin` record (sinks off) so whoever
    looks next can see whether the consumer ran."""
    t0 = time.time()
    try:
        log = Path(st["log"]) if st.get("log") else None
        tail = _tail(log, 40) if log and log.exists() else "(no log)"
        # the prompt on stdin: --allowedTools is variadic and would swallow a
        # positional prompt ("Input must be provided..." on the first e2e run)
        cmd = ["claude", "-p", "--output-format", "text", "--allowedTools", CHECKIN_TOOLS]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                             cwd=st.get("launch_cwd") or None, input=checkin_prompt(rec, st, tail))
        last = (out.stdout.strip().splitlines() or [""])[-1][:300]
        if out.returncode == 0:
            msg = f"ok ({int(time.time() - t0)} s): {last}"
        else:
            err = (out.stderr.strip().splitlines() or [last or "?"])[0][:300]
            msg = f"claude -p rc={out.returncode} ({int(time.time() - t0)} s): {err}"
    except subprocess.TimeoutExpired:
        msg = f"claude -p timed out after {timeout} s"
    except Exception as e:  # noqa: BLE001
        msg = f"claude -p failed to start: {e!r}"
    return alert(rec["run"], "checkin", f"for {rec['kind']} {rec['id']}: {msg}", st.get("dir"),
                 st.get("tag", "anvil"), sinks=False)


def claude_selftest(timeout: int = 120) -> tuple[bool, str, int]:
    """One tiny headless call at launch: is the consumer really there?"""
    t0 = time.time()
    try:
        out = subprocess.run(["claude", "-p", "--output-format", "text", "Reply with exactly the word OK."],
                             capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        secs = int(time.time() - t0)
        if out.returncode == 0 and "OK" in out.stdout:
            return True, "OK", secs
        err = ((out.stderr.strip() or out.stdout.strip()).splitlines() or ["?"])[0][:160]
        return False, f"rc={out.returncode}: {err}", secs
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout} s", timeout
    except Exception as e:  # noqa: BLE001
        return False, repr(e)[:160], int(time.time() - t0)


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
    watch = [str(w) for w in (getattr(a, "watch", None) or [])]

    def newest_artifact() -> float:
        roots = [run_dir]
        for pat in watch:
            pp = Path(pat)
            roots += list(pp.parent.glob(pp.name)) if any(c in pp.name for c in "*?[") else [pp]
        return max(newest_mtime(r) for r in roots)

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
    mode = getattr(a, "checkin_resolved", None) or checkin_mode(getattr(a, "checkin", None))
    st = {
        "name": a.name, "state": "running", "pid": child.pid, "supervisor_pid": os.getpid(),
        "started": _now(), "cmd": cmd, "dir": str(run_dir), "log": str(log),
        "stall_sec": stall_s, "tick_sec": a.tick_sec, "note": note, "tag": a.tag,
        "checkin": mode, "launch_cwd": os.getcwd(), "watch": watch,
        "nice": a.nice, "memory_max": a.memory_max, "cwd": a.cwd,
        "resume": bool(getattr(a, "resume_on_gone", False)), "resume_max": getattr(a, "resume_max", 3),
        "resume_count": getattr(a, "resume_count", 0),
    }
    _write_json(_run_file(a.name), st)
    threads: list[threading.Thread] = []
    last_checkin = [0.0]

    def checkin(rec: dict) -> None:
        """failed / stalled / long done -> the headless check-in, off-thread."""
        kind = rec["kind"]
        if mode != "claude" or kind == "recovered":
            return
        if kind == "done" and st.get("wall_s", 0) < CHECKIN_DONE_MIN_S:
            return
        if kind == "stalled" and time.time() - last_checkin[0] < CHECKIN_MIN_GAP_S:
            return
        last_checkin[0] = time.time()
        th = threading.Thread(target=llm_checkin, args=(rec, dict(st)), daemon=True)
        th.start()
        threads.append(th)

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
        newest = max(newest_artifact(), t0)
        age = time.time() - newest
        if not stalled and age > stall_s:
            stalled = True
            st.update(state="stalled", stalled_since=_now())
            _write_json(_run_file(a.name), st)
            checkin(alert(a.name, "stalled", f"no artifact under {run_dir} for {int(age // 60)} min", str(run_dir), a.tag))
        elif stalled and age <= stall_s:
            stalled = False
            st.update(state="running")
            st.pop("stalled_since", None)
            _write_json(_run_file(a.name), st)
            alert(a.name, "recovered", "fresh artifacts again", str(run_dir), a.tag)
    logf.write(f"[runs] {_now()} exit rc={rc}\n".encode())
    logf.close()
    kind = "done" if rc == 0 else "failed"
    # a `pause` marks the state file while the child drains; the exit is
    # then PAUSED (no failure push, no check-in), whatever the rc
    cur = read_run(a.name) or {}
    if cur.get("pause_requested"):
        kind = "paused"
        st["pause_requested"] = cur["pause_requested"]
        st["stop_files"] = cur.get("stop_files", [])
    st.update(state=kind, rc=rc, ended=_now(), wall_s=int(time.time() - t0))
    st.pop("stalled_since", None)
    _write_json(_run_file(a.name), st)
    tail = _tail(log)
    msg = f"rc={rc} after {st['wall_s']} s; log {log}" + ("" if kind != "failed" else f"\n{tail}")
    if kind == "paused":
        alert(a.name, "paused", msg + "; `anvil.runs relaunch --name " + a.name + "` resumes it", str(run_dir), a.tag)
    else:
        checkin(alert(a.name, kind, msg, str(run_dir), a.tag))
    for th in threads:  # the terminal event's check-in finishes before the supervisor exits
        th.join(CHECKIN_TIMEOUT_S + 30)
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
    # the check-in consumer, resolved + self-tested BEFORE the fork so the
    # coverage line can say whether anyone will answer the alerts
    mode = checkin_mode(a.checkin)
    checkin_note = mode
    if mode == "claude" and not a.no_selftest:
        ok, detail, secs = claude_selftest()
        if ok:
            checkin_note = f"claude (self-test OK, {secs} s)"
        else:
            mode = "none"
            checkin_note = f"NONE — claude -p failed the self-test: {detail}"
            alert(a.name, "checkin_unavailable", f"claude -p self-test failed: {detail} — no LLM check-in "
                  f"will run for this launch; the queue + sinks are the coverage", str(run_dir), a.tag)
    a.checkin_resolved = mode
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
        f"log {st.get('log')}, stall alarm {stall_s // 60} min on {run_dir}"
        + (f" + {' '.join(a.watch)}" if a.watch else "") + f", sinks {'+'.join(sinks)}, "
        f"check-in {checkin_note}"
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


def _stop_roots(r: dict) -> list[Path]:
    """Where a run's command looks for STOP: its dir and every --watch root
    that is a directory (a chain's arms; the harness dirs a loop launches)."""
    roots = [Path(r["dir"])] if r.get("dir") else []
    for pat in r.get("watch") or []:
        pp = Path(pat)
        roots += [q for q in (pp.parent.glob(pp.name) if any(c in pp.name for c in "*?[") else [pp]) if q.is_dir()]
    return roots


def pause(a: argparse.Namespace) -> int:
    """Stop a run on purpose (09-21): STOP in every root the command watches,
    `pause_requested` on the state so the supervisor records PAUSED (no
    FAILED push, no check-in) when the command exits; --now also SIGTERMs
    the command's process group (the harness drains, ADR-0092)."""
    r = read_run(a.name)
    if not r:
        print(f"pause: no run {a.name}", file=sys.stderr)
        return 2
    if r.get("state") not in ("running", "stalled") or not _alive(r.get("supervisor_pid")):
        print(f"pause: run {a.name} is {r.get('state')}, nothing to pause", file=sys.stderr)
        return 3
    stops = []
    for root in _stop_roots(r):
        try:
            root.mkdir(parents=True, exist_ok=True)
            (root / "STOP").write_text(f"paused by anvil.runs {_now()}\n")
            stops.append(str(root / "STOP"))
        except OSError as e:
            print(f"pause: cannot write {root / 'STOP'}: {e}", file=sys.stderr)
    r.update(pause_requested=_now(), stop_files=stops)
    _write_json(_run_file(a.name), r)
    if a.now and r.get("pid"):
        try:
            os.killpg(os.getpgid(r["pid"]), signal.SIGTERM)
        except OSError:
            try:
                os.kill(r["pid"], signal.SIGTERM)
            except OSError:
                pass
    print(f"[runs] PAUSING {a.name}: STOP in {len(stops)} root(s)" + (" + SIGTERM" if a.now else "")
          + "; the supervisor records `paused` when the command exits", flush=True)
    if a.wait:
        while (read_run(a.name) or {}).get("state") in ("running", "stalled"):
            time.sleep(5)
        print(f"[runs] {a.name}: {read_run(a.name).get('state')}")
    return 0


def _relaunch_args(r: dict, no_selftest: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        name=r["name"], dir=r["dir"], log=r.get("log"), cwd=r.get("cwd"),
        stall_min=60, stall_sec=r.get("stall_sec"), tick_sec=r.get("tick_sec", 120.0),
        nice=r.get("nice", 19), memory_max=r.get("memory_max"), tag=r.get("tag", "anvil"),
        foreground=False, checkin=r.get("checkin"), no_selftest=no_selftest, watch=r.get("watch") or [],
        resume_on_gone=bool(r.get("resume")), resume_max=r.get("resume_max", 3),
        resume_count=r.get("resume_count", 0),
    )


def relaunch(a: argparse.Namespace) -> int:
    """Re-run a paused / gone / failed / done run's recorded command in place:
    the STOP files `pause` wrote are removed, the same dir / log / watch /
    check-in; the command resumes from its own state (selfplay's
    loop_state.json, the harness's completed games)."""
    r = read_run(a.name)
    if not r:
        print(f"relaunch: no run {a.name}", file=sys.stderr)
        return 2
    if r.get("state") in ("running", "stalled") and _alive(r.get("supervisor_pid")):
        print(f"relaunch: run {a.name} is still {r['state']}", file=sys.stderr)
        return 3
    for f in r.get("stop_files") or []:
        try:
            Path(f).unlink()
        except FileNotFoundError:
            pass
    ra = _relaunch_args(r, getattr(a, "no_selftest", False))
    if r.get("launch_cwd"):
        os.chdir(r["launch_cwd"])
    print(f"[runs] RELAUNCH {a.name} (was {r.get('state')}): {' '.join(r['cmd'])}", flush=True)
    return launch(ra, list(r["cmd"]))


def sweep(a: argparse.Namespace) -> int:
    """Runs whose supervisor died (reboot, OOM, kill -9) never alert
    themselves: mark them gone, alert, check in — or, launched with
    --resume-on-gone and under the cap, relaunch them (09-21). Idempotent;
    a timer's job."""
    n = 0
    for p in (state_dir() / "runs").glob("*.json"):
        try:
            r = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if r.get("state") not in ("running", "stalled") or _alive(r.get("supervisor_pid")):
            continue
        r.update(state="gone", ended=_now())
        _write_json(p, r)
        log = Path(r["log"]) if r.get("log") else None
        tail = _tail(log) if log and log.exists() else "(no log)"
        n += 1
        if r.get("resume") and r.get("resume_count", 0) < r.get("resume_max", 3):
            r["resume_count"] = r.get("resume_count", 0) + 1
            _write_json(p, r)
            alert(r["name"], "relaunched", f"supervisor pid {r.get('supervisor_pid')} was dead (reboot / OOM / kill); "
                  f"relaunch {r['resume_count']}/{r.get('resume_max', 3)} of the recorded command", r.get("dir"),
                  r.get("tag", "anvil"))
            ra = _relaunch_args(r)
            if r.get("launch_cwd"):
                os.chdir(r["launch_cwd"])
            launch(ra, list(r["cmd"]))
            continue
        rec = alert(r["name"], "gone", f"supervisor pid {r.get('supervisor_pid')} is dead (reboot / OOM / kill); "
                    f"the run's last log lines:\n{tail}", r.get("dir"), r.get("tag", "anvil"))
        if (r.get("checkin") or checkin_mode(None)) == "claude":
            llm_checkin(rec, r)
    print(f"swept {n} gone run(s)")
    return 0


SWEEP_SERVICE = """[Unit]
Description=anvil.runs sweep — mark runs whose supervisor died, alert, check in (ADR-0107)

[Service]
Type=oneshot
WorkingDirectory={cwd}
{env}ExecStart={python} -m anvil.runs sweep
"""
SWEEP_TIMER = """[Unit]
Description=anvil.runs sweep every 10 min

[Timer]
OnBootSec=5min
OnUnitActiveSec=10min
Persistent=true

[Install]
WantedBy=timers.target
"""


def install_sweep(a: argparse.Namespace) -> int:
    """A systemd user timer for `sweep` (Linux); elsewhere print the cron line.
    Survives what the supervisor cannot: its own OOM kill, a reboot (with
    `loginctl enable-linger $USER` it runs before anyone logs in)."""
    py = sys.executable
    cwd = os.getcwd()
    if not shutil.which("systemctl") or sys.platform != "linux":
        print(f"no systemd here; add to crontab: */10 * * * * cd {cwd} && {py} -m anvil.runs sweep")
        return 0
    unit_dir = Path.home() / ".config/systemd/user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    env = "".join(f"Environment={k}={os.environ[k]}\n" for k in ("ANVIL_STATE_DIR", "ANVIL_NOTIFY_CMD", "ANVIL_CHECKIN")
                  if os.environ.get(k))  # the unit runs without a login shell: the sinks it knows are the ones written here
    (unit_dir / "anvil-runs-sweep.service").write_text(SWEEP_SERVICE.format(cwd=cwd, python=py, env=env))
    (unit_dir / "anvil-runs-sweep.timer").write_text(SWEEP_TIMER)
    for c in (["systemctl", "--user", "daemon-reload"],
              ["systemctl", "--user", "enable", "--now", "anvil-runs-sweep.timer"]):
        subprocess.run(c, check=False)
    print(f"installed {unit_dir / 'anvil-runs-sweep.timer'} (every 10 min; WorkingDirectory {cwd}); "
          f"for runs across a reboot without a login: loginctl enable-linger {os.environ.get('USER', '$USER')}")
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
    la.add_argument("--checkin", default=None, choices=["auto", "claude", "none"],
                    help="the LLM check-in on failed / stalled / gone / long done (auto = claude when the CLI "
                         "is on PATH; $ANVIL_CHECKIN overrides)")
    la.add_argument("--no-selftest", action="store_true", help="skip the launch-time claude -p self-test")
    la.add_argument("--watch", action="append", default=None, metavar="GLOB",
                    help="extra artifact roots for the stall tick (a glob; repeatable), e.g. 'data/runs/b4post-*'")
    la.add_argument("--resume-on-gone", action="store_true",
                    help="the sweep relaunches this run's recorded command when its supervisor is found dead "
                         "(a reboot, an OOM kill) — for a command that resumes from its own state, e.g. selfplay")
    la.add_argument("--resume-max", type=int, default=3, help="the relaunch cap under --resume-on-gone (a crash loop stops)")
    la.add_argument("--resume-count", type=int, default=0, help=argparse.SUPPRESS)
    pa = sub.add_parser("pause", help="write STOP for the run's command, mark it paused when it exits (no FAILED push)")
    pa.add_argument("--name", required=True)
    pa.add_argument("--now", action="store_true", help="also SIGTERM the command's process group (the harness drains its games)")
    pa.add_argument("--wait", action="store_true", help="block until the run has exited")
    rl = sub.add_parser("relaunch", help="re-run a paused / gone / failed / done run's recorded command in place (STOP files removed)")
    rl.add_argument("--name", required=True)
    rl.add_argument("--no-selftest", action="store_true")
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
    sub.add_parser("sweep")
    sub.add_parser("install-sweep")
    a = ap.parse_args(argv)
    return {"launch": lambda: launch(a, cmd), "status": lambda: status(a), "wait": lambda: wait(a),
            "alerts": lambda: alerts(a), "ack": lambda: ack(a), "prune": lambda: prune(a),
            "sweep": lambda: sweep(a), "install-sweep": lambda: install_sweep(a),
            "pause": lambda: pause(a), "relaunch": lambda: relaunch(a)}[a.verb]()


if __name__ == "__main__":
    sys.exit(main())
