#!/usr/bin/env python3
"""anvil.runs — the one launcher for long-running box jobs (ADR-0107).

The launch checklist as code: every detached run goes through
`python -m anvil.runs launch --name N --dir D -- <cmd>` and gets, by
construction, what the checklist used to ask each script to remember:

  detach      double-fork + setsid, stdin from /dev/null, the log in D
  buffering   PYTHONUNBUFFERED=1 in the child's environment
  priority    nice (default 19) on the command
  one fate    where systemd is present (Linux) the supervisor re-executes
              itself inside its own `systemd-run --user` scope and spawns the
              command there: one cgroup, ManagedOOMPreference=avoid, for both.
              They outlive the launching app and the sweep service together,
              and whatever kills the cgroup takes both, so a dead supervisor
              means a dead run (the sweep's resume rests on that). The command
              is its own session and process group, which is what a forwarded
              signal and `pause --now` reach; the supervisor is not in it.
              --memory-max adds a MemoryMax cap to the scope, ignored with a
              note elsewhere
  state       runs/<N>.json under the state dir: running -> done | failed
              (exit code, the log tail). A failure is a RECORDED state, never
              an absence — the 09-15 paired read failed in 18 s, unregistered
              cleanly and nobody knew for an hour. A supervisor that was sent
              SIGTERM / SIGINT / SIGHUP passes it to the command and records
              `failed` with the signal's name, whatever the command returned:
              a run that was told to stop did not finish.
  stall       the supervisor (this process, alive for the run's whole life)
              ticks on the newest mtime under D: running -> stalled ->
              recovered, on transition only. The launcher's own files do not
              count (11-09: the memory sampler's memory.jsonl, the supervisor's
              log — stall_ignored); heartbeat.json does. THE WRITERS' RULE the
              tick rests on: nothing under a watched dir is written on a timer
              unless it is a deliberate wait, and a deliberate wait heartbeats.
              A helper that prints "still nothing" every minute blinds the tick
              (the model server's idle stats line and the harness's unchanged
              progress line did, through every generation, until 11-09)
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
              the events that need a human: failed, stalled, gone, orphaned,
              and done after > 1 h — it pushes to the phone, messages the supervising
              desktop session, acks the alert. Event-driven: no polling task
              to remember to enable. `--checkin auto|claude|none` (auto =
              claude when the CLI is on PATH; $ANVIL_CHECKIN overrides); the
              launch runs a self-test so a missing consumer (no CLI, an
              expired login) shows in the coverage line, not the next morning
  watch       --watch <glob> (repeatable) adds artifact roots to the stall
              tick beside --dir: a read chain launched from its own dir writes
              its arms under data/runs/<name>-* and raised two false stalls
              on 09-17 — name those roots and the tick sees them
  pause       `anvil.runs pause --name N [--now] [--wait] [--scope loop|all]` (09-21): STOP in the
              run dir + every watched LOOP root (09-27: never a loop's live
              harness dirs — the generation finishes, the loop stops at its
              boundary; --scope all = every watched dir) + `pause_requested`
              on the state; the supervisor records PAUSED at exit (no FAILED
              push, no check-in).
  relaunch    `anvil.runs relaunch --name N`: the recorded command again, in
              place (STOP files removed); `--resume-on-gone` at launch lets
              the sweep do this itself after a reboot, capped by --resume-max.
              The check-in is resolved and self-tested again on every relaunch
              from the mode the run was launched with (11-09: one expired login
              no longer turns it off for the run's life); --checkin overrides.
  sweep       `anvil.runs sweep` marks runs whose supervisor died (reboot,
              OOM, kill -9) as gone, alerts, checks in; `install-sweep` puts
              it on a systemd user timer (10 min) where systemd exists
  orphaned    a run whose supervisor is dead while its command (the recorded
              pid, or anything left in its scope) is alive. The sweep records
              it, alerts once, checks in and leaves it alone; `launch` and
              `relaunch` refuse it. Nothing starts a second copy beside a live
              one. When the orphan exits it reads `gone` and is never resumed
              automatically: its exit was not observed.
  dir lock    `hold_dir_lock(dir)` is the last line under the guards: an
              exclusive flock a worker of a directory takes for its own life
              (the self-play loop on <out>/loop.lock), so two processes cannot
              work one directory whatever started the second

No registry, no timer, no per-run waiter: one supervisor per run is its own
watchdog. Stdlib only, zero repo imports — it must keep working while the
tree is mid-run-frozen or broken (the watchd rule). Portable: Linux / macOS
(no systemd, no /proc needed).

Verbs:
  launch  --name N --dir D [--stall-min 60] [--nice 19] [--memory-max 20G]
          [--log D/run.log] [--tick-sec 120] -- cmd...
  status  [--json]                 every run's state (newest first)
  wait    --name N [--timeout S]   block until the run stops being supervised; exit 0 done, 1 failed,
                                   2 gone (dead supervisor), 3 the --timeout, 4 paused, 5 orphaned
  tick    --name N                 read-only: what the stall tick sees right now (exit 1 = it would read stalled)
  alerts  [--unacked] [--json]     the queue
  ack     --all | --id ID...       mark alerts read
  prune   [--days 30]              drop terminal run records older than N days
  sweep                            mark gone and orphaned runs (dead supervisor), alert, check in
  install-sweep                   a systemd user timer for sweep (Linux); a cron line elsewhere
State dir: $ANVIL_STATE_DIR, else ~/.local/state/anvil.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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


# 11-09 (the infrastructure survey, finding 1): files the launcher's own machinery
# writes into a run dir are not the run's artifacts. The memory sampler appends
# <run dir>/memory.jsonl every 20 s, so the stall tick saw a fresh file forever
# (zero `stalled` alerts for the big run in five weeks, through a 91-minute
# training-step wait and whatever else went quiet); and the detached supervisor's
# own stdout is <run dir>/supervisor.log, so raising STALLED refreshed the dir and
# the next tick called it `recovered` (every stall in the queue up to 11-09 is
# followed by a recovery exactly one tick later). heartbeat.json is NOT here: a
# job idle on purpose is alive, that is the heartbeat's whole point.
STALL_IGNORE_NAMES = ("memory.jsonl", "supervisor.log")


def stall_ignored(run_dir: Path) -> frozenset[str]:
    """The absolute paths the stall tick skips: this run's own sampler output and
    supervisor log, plus wherever the box's one memory sampler is writing right
    now (memsampler.json `out` — it may be another run's dir that sits under one
    of this run's --watch roots)."""
    own = {os.path.realpath(run_dir / n) for n in STALL_IGNORE_NAMES}
    try:
        out = json.loads((state_dir() / "memsampler.json").read_text()).get("out")
        if out:
            own.add(os.path.realpath(out))
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    return frozenset(own)


def newest_file(root: Path, ignore: frozenset[str] = frozenset()) -> tuple[float, str | None]:
    """(mtime, path) of the newest file under root (the run's own artifact dir,
    not a project-wide tree); (0, None) when nothing is there yet. `ignore` =
    real paths that do not count (stall_ignored); only a file whose basename
    matches one is resolved, so the walk stays a walk."""
    names = {os.path.basename(p) for p in ignore}

    def skipped(path: str, fn: str) -> bool:
        return fn in names and os.path.realpath(path) in ignore

    newest, which = 0.0, None
    try:
        if os.path.isfile(root):  # a --watch glob may name files
            if skipped(str(root), os.path.basename(root)):
                return 0.0, None
            return os.stat(root).st_mtime, str(root)
        for dirpath, _dirs, files in os.walk(root):
            for fn in files:
                path = os.path.join(dirpath, fn)
                if skipped(path, fn):
                    continue
                try:
                    m = os.stat(path).st_mtime
                except OSError:
                    continue
                if m > newest:
                    newest, which = m, path
    except OSError:
        pass
    return newest, which


def newest_mtime(root: Path, ignore: frozenset[str] = frozenset()) -> float:
    return newest_file(root, ignore)[0]


def stall_roots(run_dir: Path, watch: list[str], base: Path | None = None) -> list[Path]:
    """The run dir plus every --watch root (globs expanded now: a chain's arm
    dirs appear as it goes). `base` anchors a relative pattern for a reader
    that is not in the supervisor's cwd (the `tick` verb)."""
    roots = [run_dir]
    for pat in watch:
        pp = Path(pat)
        if base is not None and not pp.is_absolute():
            pp = base / pp
        roots += list(pp.parent.glob(pp.name)) if any(c in pp.name for c in "*?[") else [pp]
    return roots


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


def _relay_rule(st: dict) -> str:
    """Step 3 of the check-in: who gets the event (10-03). The launching session
    owns the run's close, so the relay wakes it and nobody else; the broadcast
    to every 'anvil' session (09-18) woke the idle remote-control sessions in
    the main checkout, which wrote their own closes on 10-01 and 10-03 while
    the launcher — a bridge worktree session whose name has no 'anvil' — was
    never messaged."""
    who = st.get("launched_by")
    fallback = ("to the most recently started interactive session whose name or title contains \"anvil\" "
                "(case-insensitive), or, if there is none, to the most recently started interactive session")
    if who:
        # 10-04: a session's own "This session is <name> [<ref>]" name is NOT what peers see —
        # a session with a conversation title is listed by that title; only the bracketed ref
        # is the same from every side (the 10-03/10-04 relays reported the launcher "not
        # listed" and fell back, while its row sat there under its title). Match the ref.
        m = re.search(r"\[([0-9a-f]{4,})\]", who)
        key = (f"whose row carries the ref [{m.group(1)}] (the bracketed id; the row's name or title may differ)"
               if m else f"named \"{who}\" — or, if no row has that name, whose row carries that text as its ref")
        return (f"With SendMessage, send ONE message to the session {key}: the session that launched this run. "
                f"Only if no row matches, send it {fallback}.")
    return f"With SendMessage, send ONE message {fallback} (this run recorded no launching session)."


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
        "3. Call ListAgents. " + _relay_rule(st) + " The message: the event kind, the run name, the state "
        "file, the log path and the error lines, then this sentence verbatim: \"The session that launched this "
        "run owns its record; if you are not that session, do not write its close (running record, Now block, "
        "map, devlog) — read the state file and leave the record to the launcher.\" Do not ask them questions.\n"
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


# ------------------------------------------------- the run's scope, and liveness

SPEC_ENV = "ANVIL_RUNS_SPEC"   # the launch's arguments, handed to the re-executed supervisor
START_WAIT_S = 30.0            # how long `launch` waits for the supervisor's first state write
LIVE_STATES = ("running", "stalled", "orphaned")


def _systemd_user() -> bool:
    return sys.platform.startswith("linux") and bool(shutil.which("systemd-run"))


def scope_unit(name: str, supervisor_pid: int) -> str:
    """The run's scope is named after its supervisor's pid: one name per launch."""
    return f"anvil-{name}-{supervisor_pid}.scope"


def _scope_argv(unit: str, memory_max: str | None, name: str) -> list[str]:
    """The supervisor, re-executed inside its own `systemd-run --user` scope
    (docs/ops/infra-survey-2026-11-09.md, finding 4). `systemd-run --scope`
    moves the calling process into the new cgroup and then execs the command
    in place, so the supervisor keeps the pid the unit is named after, and the
    command it spawns is born in the same cgroup. One scope for both is the
    point: a kill of the launching app or of the sweep's service reaches
    neither, and a kill of the scope reaches both. ManagedOOMPreference=avoid
    makes oomd prefer the desktop on a memory-pressure kill; it is not honoured
    for a swap-limit kill on a user-owned cgroup (systemd.resource-control(5)),
    where scripts/memory_sampler.sh is the defence. Nice is not a scope
    property; the supervisor sets it on the command.

    This file is run as a script under -P: the supervisor is the launcher's own
    code whatever the cwd, and the script's directory never shadows the stdlib.
    The launch's arguments travel in the environment (SPEC_ENV), not on the
    command line, so a `pgrep -f` for the run's command does not match the
    supervisor."""
    props = ["-p", "ManagedOOMPreference=avoid"]
    if memory_max:
        props += ["-p", f"MemoryMax={memory_max}"]
    return (["systemd-run", "--user", "--scope", "--quiet", f"--unit={unit.removesuffix('.scope')}"] + props
            + [sys.executable, "-P", str(Path(__file__).resolve()), "_supervise", name])


def _scope_active(unit: str) -> bool:
    """A scope is active for as long as one process is left in it."""
    try:
        return subprocess.run(["systemctl", "--user", "is-active", "--quiet", unit],
                              capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _proc_stat(pid: int) -> tuple[str, int] | None:
    """(state letter, start time in clock ticks since boot) from /proc/<pid>/stat;
    None where there is no /proc or no such pid. The start time, with the pid,
    is an identity a reused pid number does not share."""
    try:
        f = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return f[0], int(f[19])
    except (OSError, IndexError, ValueError):
        return None


def _pid_start(pid: int | None) -> int | None:
    st = _proc_stat(pid) if pid else None
    return st[1] if st else None


def _same_process(pid: int | None, start: int | None) -> bool:
    """Is `pid` alive and still the process that was recorded with that start
    time? A zombie is not alive. Without /proc the pid alone decides."""
    if not _alive(pid):
        return False
    st = _proc_stat(pid)
    if st is None:
        return True
    return st[0] != "Z" and (start is None or st[1] == start)


def run_scope(r: dict) -> str | None:
    """The scope a run's processes live in. A state file from before the field
    was recorded names it the same way, after the supervisor's pid."""
    if "scope" in r:
        return r["scope"]
    if r.get("name") and r.get("supervisor_pid") and _systemd_user():
        return scope_unit(r["name"], r["supervisor_pid"])
    return None


def command_alive(r: dict) -> str | None:
    """What is still alive of a run's command: the recorded pid, or anything
    left in its scope (the command's own children outlive it there). A phrase
    naming it, or None."""
    if _same_process(r.get("pid"), r.get("pid_start")):
        return f"pid {r['pid']}"
    unit = run_scope(r)
    if unit and _scope_active(unit):
        return f"scope {unit}"
    return None


def liveness(r: dict | None) -> str:
    """supervised | orphaned | dead — the one question every verb asks before
    it starts, stops or reports a run. `orphaned` is a dead supervisor over a
    live command: nothing may be launched beside it."""
    if not r or r.get("state") not in LIVE_STATES:
        return "dead"
    if r["state"] != "orphaned" and _alive(r.get("supervisor_pid")):
        return "supervised"
    return "orphaned" if command_alive(r) else "dead"


def _orphan_advice(r: dict) -> str:
    unit = run_scope(r)
    stop = f"`systemctl --user stop {unit}`" if unit else f"`kill {r.get('pid')}`"
    return f"stop it ({stop}) or let it finish, then `anvil.runs relaunch --name {r.get('name')}`"


# ------------------------------------------------------------ the directory lock


class DirLocked(RuntimeError):
    """Another live process holds the directory's lock."""


def hold_dir_lock(d: Path, name: str = "loop.lock"):
    """Take <d>/<name> exclusively, without waiting, and return the open file.
    The lock lasts as long as that file object: keep the reference for the
    process's life. It is a flock, so the kernel drops it when the process
    dies however it dies, and no stale lock can exist; the file's text (the
    holder's pid) is for the reader of a refusal. Children do not inherit it:
    Python opens files close-on-exec. Raises DirLocked when another process
    holds it."""
    import fcntl

    f = open(Path(d) / name, "a+")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.seek(0)
        holder = f.read().strip() or "an unnamed process"
        f.close()
        raise DirLocked(f"{Path(d) / name} is held by {holder}") from None
    f.seek(0)
    f.truncate()
    f.write(f"pid {os.getpid()} since {_now()}\n")
    f.flush()
    return f


MEMSAMPLER_UNIT = os.environ.get("ANVIL_MEMSAMPLER_UNIT", "anvil-memsampler")


def arm_memsampler(name: str, run_dir: Path, run=subprocess.run) -> str:
    """10-29 (the user's question at the segment-3 boundary): the memory
    sampler + watchdog (scripts/memory_sampler.sh) is a TRANSIENT user unit —
    it dies with every reboot, and every long run depends on it (two oomd kills
    of the big run before it existed; it was re-armed by hand on 10-21 and
    forgotten after the 10-29 reboot). So the launcher arms it, not a hand or a
    chain: a checklist item as code (ADR-0107). Active and armed by a run that
    is still live (or by this run: a relaunch) → left alone — one unit, one
    box; active for a run that has finished, or inactive → (re)started with
    this run's dir as its output (<dir>/memory.jsonl; <dir>/WATCHDOG-TRIP is
    what the big-run chain's retry reads). Returns the coverage phrase and
    never raises: a box without systemd runs unwatched, and the line says so.
    ANVIL_MEMSAMPLER=0 turns it off (tests, Macs)."""
    if os.environ.get("ANVIL_MEMSAMPLER", "1") == "0":
        return "memory watchdog: off (ANVIL_MEMSAMPLER=0)"
    if not shutil.which("systemd-run") or not sys.platform.startswith("linux"):
        return "memory watchdog: unavailable (no systemd on this platform)"
    script = Path(__file__).resolve().parents[1] / "scripts" / "memory_sampler.sh"
    if not script.exists():
        return f"memory watchdog: unavailable ({script} missing)"
    rec_p = state_dir() / "memsampler.json"
    try:
        rec = json.loads(rec_p.read_text())
    except (OSError, json.JSONDecodeError):
        rec = {}
    active = run(["systemctl", "--user", "is-active", "--quiet", MEMSAMPLER_UNIT], capture_output=True).returncode == 0
    if active:
        owner = rec.get("run")
        own = read_run(owner) if owner and owner != name else None
        if owner == name or liveness(own) != "dead":  # an orphaned owner still trains: it keeps the watchdog
            return f"memory watchdog: active (armed by {owner} -> {rec.get('out')})"
        run(["systemctl", "--user", "stop", MEMSAMPLER_UNIT], capture_output=True)
    run(["systemctl", "--user", "reset-failed", MEMSAMPLER_UNIT], capture_output=True)
    out = run_dir / "memory.jsonl"
    r = run(["systemd-run", "--user", f"--unit={MEMSAMPLER_UNIT}", "-p", "MemoryMax=500M",
             "-p", f"WorkingDirectory={script.parents[1]}", "/usr/bin/bash", str(script), str(out), "20"],
            capture_output=True, text=True)
    if r.returncode != 0:
        err = (getattr(r, "stderr", "") or "").strip()[:120]
        return f"memory watchdog: FAILED to arm (systemd-run rc {r.returncode}: {err}) — the run is unwatched"
    _write_json(rec_p, {"run": name, "out": str(out), "armed": _now()})
    return f"memory watchdog: ARMED -> {out}"


def _base_state(a: argparse.Namespace, cmd: list[str], run_dir: Path, log: Path) -> dict:
    """The fields of a state file that a relaunch reads back, whatever the
    launch came to (supervise fills in the live ones; a supervisor that never
    started still leaves a record `relaunch` can use)."""
    return {
        "name": a.name, "cmd": cmd, "dir": str(run_dir), "log": str(log),
        "stall_sec": a.stall_sec if a.stall_sec is not None else a.stall_min * 60,
        "tick_sec": a.tick_sec, "tag": a.tag,
        "checkin_requested": getattr(a, "checkin", None) or "auto",
        "launch_cwd": os.getcwd(), "watch": [str(w) for w in (getattr(a, "watch", None) or [])],
        "launched_by": getattr(a, "launched_by", None) or None,
        "nice": a.nice, "memory_max": a.memory_max, "cwd": a.cwd,
        "resume": bool(getattr(a, "resume_on_gone", False)), "resume_max": getattr(a, "resume_max", 3),
        "resume_count": getattr(a, "resume_count", 0),
    }


def supervise(a: argparse.Namespace, cmd: list[str]) -> int:
    """The supervisor: spawn the command, tick the stall check, write the
    terminal state, alert on every transition. Detached, it runs inside the
    run's own scope (`a.scope`, see _scope_argv) and the command is born
    there; in the foreground, or without systemd, there is no scope."""
    run_dir = Path(a.dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    log = Path(a.log).resolve() if a.log else run_dir / "run.log"
    env = dict(os.environ, PYTHONUNBUFFERED="1", ANVIL_RUN_NAME=a.name)
    scope = getattr(a, "scope", None)
    note = None
    if a.memory_max and not scope:
        note = f"--memory-max {a.memory_max} ignored: the run is not in a systemd scope"
    stall_s = a.stall_sec if a.stall_sec is not None else a.stall_min * 60
    watch = [str(w) for w in (getattr(a, "watch", None) or [])]

    def newest_artifact() -> float:
        ignore = stall_ignored(run_dir)  # re-read each tick: the sampler's owner can change
        return max(newest_mtime(r, ignore) for r in stall_roots(run_dir, watch))

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

    mode = getattr(a, "checkin_resolved", None) or checkin_mode(getattr(a, "checkin", None))
    # `checkin` = what this launch RESOLVED to (the sweep's and a reader's view);
    # `checkin_requested` = what was asked, which is what a relaunch resolves again
    st = dict(_base_state(a, cmd, run_dir, log), supervisor_pid=os.getpid(), started=_now(),
              note=note, checkin=mode, scope=scope)
    try:
        # The command is its own session, so its own process group: a signal the
        # supervisor passes on (and `pause --now`) reaches the command's whole tree
        # and never the supervisor. In one group, the handler below signalled itself
        # and re-entered until the recursion limit (the survey's finding 13).
        child = subprocess.Popen(
            cmd, stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            env=env, cwd=a.cwd or None, preexec_fn=preexec, start_new_session=True,
        )
    except Exception as e:  # noqa: BLE001
        st.update(state="failed", rc=-1, ended=_now(), error=f"spawn failed: {e}")
        _write_json(_run_file(a.name), st)
        alert(a.name, "failed", f"spawn failed: {e}", str(run_dir), a.tag)
        return 1
    # pid_start: with the pid, the command's identity for the orphan check (command_alive)
    st.update(state="running", pid=child.pid, pid_start=_pid_start(child.pid))
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

    signalled: list[int] = []

    def forward(signum, _frame):  # noqa: ANN001
        signalled.append(signum)
        if child.returncode is not None:
            return
        try:
            os.killpg(child.pid, signum)  # the command leads its own group
        except OSError:
            pass

    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s, forward)

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
    # A supervisor that was told to stop did not see a run finish, whatever the
    # command returned on its way down: never `done`.
    sig = signal.Signals(signalled[0]).name if signalled else None
    kind = "done" if rc == 0 and sig is None else "failed"
    # a `pause` marks the state file while the child drains; the exit is
    # then PAUSED (no failure push, no check-in), whatever the rc
    cur = read_run(a.name) or {}
    if cur.get("pause_requested"):
        kind = "paused"
        st["pause_requested"] = cur["pause_requested"]
        st["stop_files"] = cur.get("stop_files", [])
    st.update(state=kind, rc=rc, ended=_now(), wall_s=int(time.time() - t0))
    if sig:
        st["signal"] = sig
    st.pop("stalled_since", None)
    _write_json(_run_file(a.name), st)
    tail = _tail(log)
    msg = ((f"the supervisor was sent {sig} and passed it to the command; " if sig else "")
           + f"rc={rc} after {st['wall_s']} s; log {log}" + ("" if kind != "failed" else f"\n{tail}"))
    if kind == "paused":
        alert(a.name, "paused", msg + "; `anvil.runs relaunch --name " + a.name + "` resumes it", str(run_dir), a.tag)
    else:
        checkin(alert(a.name, kind, msg, str(run_dir), a.tag))
    for th in threads:  # the terminal event's check-in finishes before the supervisor exits
        th.join(CHECKIN_TIMEOUT_S + 30)
    return 0 if rc == 0 and sig is None else 1


def _supervise_entry() -> int:
    """`runs.py _supervise <name>`: the supervisor as its own process, started
    by _scope_argv inside the run's scope. The launch's arguments arrive in
    SPEC_ENV and leave the environment before the command is spawned."""
    spec = json.loads(os.environ.pop(SPEC_ENV))
    a = argparse.Namespace(**spec["args"])
    a.scope = spec.get("scope")
    return supervise(a, spec["cmd"])


def _spawn_supervisor(a: argparse.Namespace, cmd: list[str], run_dir: Path) -> int | None:
    """Detach the supervisor and return its pid (None when the fork chain broke).
    Double fork + setsid: it is nobody's child and holds no terminal. With
    systemd it then execs itself into the run's scope; elsewhere it supervises
    in the forked process."""
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        code = 1
        try:
            os.close(r)
            os.setsid()
            if os.fork() != 0:
                os._exit(0)
            os.write(w, str(os.getpid()).encode())
            os.close(w)
            devnull = os.open(os.devnull, os.O_RDWR)
            os.dup2(devnull, 0)
            sup_log = open(run_dir / "supervisor.log", "ab")
            os.dup2(sup_log.fileno(), 1)
            os.dup2(sup_log.fileno(), 2)
            if _systemd_user():
                unit = scope_unit(a.name, os.getpid())
                spec = json.dumps({"args": vars(a), "cmd": cmd, "scope": unit}, default=str)
                argv = _scope_argv(unit, a.memory_max, a.name)
                try:
                    os.execvpe(argv[0], argv, dict(os.environ, **{SPEC_ENV: spec}))
                except OSError as e:
                    os.write(2, f"[runs] cannot exec {argv[0]}: {e}\n".encode())
                    code = 127
            else:
                code = supervise(a, cmd)
        finally:
            os._exit(code)
    os.close(w)
    with os.fdopen(r) as f:
        got = f.read().strip()
    os.waitpid(pid, 0)
    return int(got) if got.isdigit() else None


def launch(a: argparse.Namespace, cmd: list[str]) -> int:
    if not cmd:
        print("launch: no command after --", file=sys.stderr)
        return 2
    prev = read_run(a.name)
    live = liveness(prev)
    if live == "supervised":
        print(f"launch: run {a.name} is still {prev['state']} (supervisor pid {prev['supervisor_pid']})",
              file=sys.stderr)
        return 3
    if live == "orphaned":
        # the guard under every path that could start a second copy: a hand, a chain, the sweep
        print(f"launch: run {a.name} is orphaned — its supervisor is dead and its command is still alive "
              f"({command_alive(prev)}); {_orphan_advice(prev)}", file=sys.stderr)
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
    # 10-29: the memory watchdog is armed by every detached launch (relaunch included)
    mem_note = ("memory watchdog: off (--no-memsampler)" if getattr(a, "no_memsampler", False)
                else arm_memsampler(a.name, run_dir))
    sup = _spawn_supervisor(a, cmd, run_dir)
    # wait for THIS supervisor's first state write; one that dies first is a recorded failure
    st: dict = {}
    deadline = time.time() + START_WAIT_S
    while sup is not None and time.time() < deadline:
        st = read_run(a.name) or {}
        if st.get("supervisor_pid") == sup:
            break
        st = {}
        if not _same_process(sup, None):
            st = read_run(a.name) or {}  # it may have written and exited between the two reads
            if st.get("supervisor_pid") != sup:
                st = {}
            break
        time.sleep(0.05)
    if not st and (sup is None or not _same_process(sup, None)):
        log = Path(a.log).resolve() if a.log else run_dir / "run.log"
        err = "the supervisor did not start: " + (_tail(run_dir / "supervisor.log", 3).replace("\n", " | ") or "no output")
        st = dict(_base_state(a, cmd, run_dir, log), state="failed", rc=-1, started=_now(), ended=_now(),
                  error=err, supervisor_pid=sup, checkin=mode)
        _write_json(_run_file(a.name), st)
        alert(a.name, "failed", err, str(run_dir), a.tag)
        print(f"[runs] NOT LAUNCHED {a.name}: {err}", file=sys.stderr, flush=True)
        return 1
    if not st:
        print(f"[runs] UNCONFIRMED {a.name}: supervisor pid {sup} is alive and wrote no state in "
              f"{int(START_WAIT_S)} s; read {run_dir / 'supervisor.log'} and `anvil.runs status`", file=sys.stderr, flush=True)
        return 1
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
        f"check-in {checkin_note}, relay to "
        + (f"{st['launched_by']}" if st.get("launched_by") else "UNSET (any live anvil session; pass --launched-by)")
        + f", {mem_note}"
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
        if r.get("state") in LIVE_STATES:
            live = liveness(r)
            if live != "supervised":  # the supervisor died (reboot, kill): not a clean exit
                r["state"] = "orphaned" if live == "orphaned" else "gone"
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


# `wait`'s exit codes, one per way a run stops being live (3 = the wait's own --timeout)
WAIT_RC = {"done": 0, "failed": 1, "gone": 2, "paused": 4, "orphaned": 5}


def wait(a: argparse.Namespace) -> int:
    t0 = time.time()
    while True:
        # 10-03: a queue that waits inside a launched run is alive by construction —
        # its own dir gets a heartbeat (a no-op outside a launched run), so the
        # supervisor's stall tick stops raising the false-stall class on queues
        # (after-paired STALLED at 240 min, 22:45, four hours into a benign wait).
        heartbeat(f"waiting on {a.name}")
        r = read_run(a.name)
        state = (r or {}).get("state")
        if state in ("done", "failed"):
            print(f"{a.name}: {state} rc={r.get('rc')}")
            return WAIT_RC[state]
        # 11-09 (survey finding 7): every terminal state ends the wait. `paused` and a `gone`
        # the sweep had already written matched no branch, so the launching session's
        # background wait — the belt under the check-in — hung forever on exactly those two.
        if state in ("paused", "gone"):
            print(f"{a.name}: {state}" + (" (the sweep found the supervisor dead)" if state == "gone" else
                                         f" — `anvil.runs relaunch --name {a.name}` resumes it"))
            return WAIT_RC[state]
        if state in LIVE_STATES and liveness(r) != "supervised":
            # a dead supervisor ends the wait either way: nothing will write a later state
            alive = command_alive(r)
            if alive:
                print(f"{a.name}: orphaned (supervisor died; the command is still alive: {alive}) — "
                      + _orphan_advice(r))
                return WAIT_RC["orphaned"]
            print(f"{a.name}: gone (supervisor died)")
            return WAIT_RC["gone"]
        if a.timeout and time.time() - t0 > a.timeout:
            print(f"{a.name}: wait timeout")
            return 3
        time.sleep(a.poll)


def tick(a: argparse.Namespace) -> int:
    """What the supervisor's stall tick sees for a run RIGHT NOW, read-only (11-09): the
    newest file it counts and that file's age against the alarm, and the files it does
    not count with theirs. The check after a relaunch that the tick is looking at the
    run and not at the launcher's own writes — it touches nothing, signals nothing, and
    is safe on a live run. Exit 0 = the tick reads running, 1 = it would read stalled,
    2 = no such run."""
    r = read_run(a.name)
    if not r or not r.get("dir"):
        print(f"tick: no run {a.name}", file=sys.stderr)
        return 2
    run_dir = Path(r["dir"])
    ignore = stall_ignored(run_dir)
    base = Path(r["launch_cwd"]) if r.get("launch_cwd") else None
    newest, which = 0.0, None
    for root in stall_roots(run_dir, r.get("watch") or [], base):
        m, f = newest_file(root, ignore)
        if m > newest:
            newest, which = m, f
    try:  # the supervisor never counts silence from before its own start
        started = datetime.fromisoformat(r["started"]).timestamp()
    except (KeyError, TypeError, ValueError):
        started = 0.0
    now = time.time()
    stall_s = r.get("stall_sec") or 3600
    age = now - max(newest, started)
    would = age > stall_s
    print(f"{a.name}: state {r.get('state')}; newest counted artifact {which or '(none)'}"
          + (f", {int(now - newest)} s old" if newest else "")
          + f"; the alarm is at {stall_s} s; the tick reads {'STALLED' if would else 'running'} "
          f"({int(age)} s of silence since the later of that file and the launch)")
    for p in sorted(ignore):
        try:
            print(f"  not counted: {p} ({int(now - os.stat(p).st_mtime)} s old)")
        except OSError:
            continue
    return 1 if would else 0


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


def _watch_dirs(r: dict) -> list[Path]:
    """Every --watch root that is a directory (a chain's arms; the harness
    dirs a loop launches)."""
    roots: list[Path] = []
    for pat in r.get("watch") or []:
        pp = Path(pat)
        roots += [q for q in (pp.parent.glob(pp.name) if any(c in pp.name for c in "*?[") else [pp]) if q.is_dir()]
    return roots


def _is_loop_root(d: Path) -> bool:
    return (d / "loop_state.json").exists()


def _is_harness_dir(d: Path) -> bool:
    """A harness run dir: its pinning manifest is `run.json` (orchestrator.py;
    the 09-27 check keyed on `manifest.json`, a name the harness never writes,
    so the 09-28 pause wrote STOP into the anchor cell's live generation half —
    44 roots — and it drained at 25/120; the test had faked the wrong file)."""
    return ((d / "run.json").exists() or (d / "manifest.json").exists()) and (d / "workers").is_dir()


def _stop_roots(r: dict, scope: str = "loop") -> list[Path]:
    """Where `pause` writes STOP. scope="loop" (the default since 09-27): the
    run's dir, every watched selfplay loop root (loop_state.json) and, when NO
    loop root is watched, every other watched dir too (a harness-only run
    drains at game granularity). A loop's harness dirs (manifest.json +
    workers/) are SKIPPED whenever a loop root is present: the 09-23 pause
    wrote STOP into the alloc arm's live generation, the harness honoured it
    at 34/240 games and the loop trained a 57% iteration inside an intact
    budget (the loop itself stops at its iteration boundary; the generation
    must finish). scope="all" = the 09-21 behaviour, every root."""
    roots = [Path(r["dir"])] if r.get("dir") else []
    watched = _watch_dirs(r)
    if scope == "all":
        return roots + watched
    loops = [d for d in watched if _is_loop_root(d)]
    if loops:
        return roots + loops + [d for d in watched if not _is_loop_root(d) and not _is_harness_dir(d)]
    return roots + watched


def pause(a: argparse.Namespace) -> int:
    """Stop a run on purpose (09-21): STOP in the roots `_stop_roots` names
    (09-27: the loop roots, never a loop's live generation — --scope all for
    every watched dir), `pause_requested` on the state so the supervisor
    records PAUSED (no FAILED push, no check-in) when the command exits;
    --now also SIGTERMs the command's process group: every process of the
    run's tree receives it itself, and the supervisor, which is outside that
    group, does not."""
    r = read_run(a.name)
    if not r:
        print(f"pause: no run {a.name}", file=sys.stderr)
        return 2
    live = liveness(r)
    if live == "orphaned":
        print(f"pause: run {a.name} is orphaned ({command_alive(r)} alive, no supervisor to record a pause); "
              + _orphan_advice(r), file=sys.stderr)
        return 3
    if live != "supervised":
        print(f"pause: run {a.name} is {r.get('state')}, nothing to pause", file=sys.stderr)
        return 3
    stops = []
    for root in _stop_roots(r, getattr(a, "scope", "loop")):
        try:
            root.mkdir(parents=True, exist_ok=True)
            (root / "STOP").write_text(f"paused by anvil.runs {_now()}\n")
            stops.append(str(root / "STOP"))
        except OSError as e:
            print(f"pause: cannot write {root / 'STOP'}: {e}", file=sys.stderr)
    r.update(pause_requested=_now(), stop_files=stops)
    _write_json(_run_file(a.name), r)
    if a.now and r.get("pid"):
        try:  # the command's own group (it leads one): its whole tree, never the supervisor
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


def _relaunch_args(r: dict, no_selftest: bool = False, launched_by: str | None = None,
                   checkin: str | None = None) -> argparse.Namespace:
    # 10-21: `launched_by` overrides the recorded session (a relaunch from a new session: the
    # recorded ref is a dead session's and the check-in relay would fall back); None keeps it
    # 11-09 (survey finding 2): the check-in is resolved AGAIN from the REQUESTED mode, never
    # from the last launch's resolution. The big run's 10-16 relaunch met an expired login,
    # recorded `checkin: none`, and every relaunch for four weeks passed that `none` back in —
    # five failures and three segment closes with no check-in after the login was restored.
    # `checkin` (relaunch --checkin) overrides; a state file from before this field has no
    # request on record and resolves as auto (`relaunch --checkin none` keeps one off).
    requested = checkin or r.get("checkin_requested") or "auto"
    return argparse.Namespace(
        name=r["name"], dir=r["dir"], log=r.get("log"), cwd=r.get("cwd"),
        stall_min=60, stall_sec=r.get("stall_sec"), tick_sec=r.get("tick_sec", 120.0),
        nice=r.get("nice", 19), memory_max=r.get("memory_max"), tag=r.get("tag", "anvil"),
        foreground=False, checkin=requested, no_selftest=no_selftest, watch=r.get("watch") or [],
        resume_on_gone=bool(r.get("resume")), resume_max=r.get("resume_max", 3),
        resume_count=r.get("resume_count", 0), launched_by=launched_by or r.get("launched_by"),
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
    live = liveness(r)
    if live == "supervised":
        print(f"relaunch: run {a.name} is still {r['state']}", file=sys.stderr)
        return 3
    if live == "orphaned":  # before the STOP files go: a refused relaunch changes nothing
        print(f"relaunch: run {a.name} is orphaned — its supervisor is dead and its command is still alive "
              f"({command_alive(r)}); {_orphan_advice(r)}", file=sys.stderr)
        return 3
    for f in r.get("stop_files") or []:
        try:
            Path(f).unlink()
        except FileNotFoundError:
            pass
    ra = _relaunch_args(r, getattr(a, "no_selftest", False), getattr(a, "launched_by", None),
                        getattr(a, "checkin", None))
    if r.get("checkin") == "none" and ra.checkin != "none":
        print(f"[runs] RELAUNCH {a.name}: the last launch ran with no check-in; resolving {ra.checkin!r} again",
              flush=True)
    # 11-09 (survey finding 9): a relaunch by hand is someone looking at the run, so the
    # sweep's resume budget starts over. The cap exists to stop a crash LOOP; carried through
    # every manual relaunch it was a budget for the run's whole life (the big run spent 1 of
    # its 3 on 10-10 and still carried it four weeks and a dozen relaunches later). The
    # sweep's own resume does not come through here and keeps counting.
    if ra.resume_count:
        print(f"[runs] RELAUNCH {a.name}: resume count {ra.resume_count}/{ra.resume_max} -> 0 (a manual relaunch)",
              flush=True)
        ra.resume_count = 0
    if r.get("launch_cwd"):
        os.chdir(r["launch_cwd"])
    if ra.launched_by != r.get("launched_by"):
        print(f"[runs] RELAUNCH {a.name}: launched_by {r.get('launched_by')!r} -> {ra.launched_by!r}", flush=True)
    print(f"[runs] RELAUNCH {a.name} (was {r.get('state')}): {' '.join(r['cmd'])}", flush=True)
    return launch(ra, list(r["cmd"]))


def sweep(a: argparse.Namespace) -> int:
    """Runs whose supervisor died never alert themselves. Idempotent; a
    timer's job. Three readings of a dead supervisor:

    orphaned  the command is still alive (command_alive). Recorded, one alert,
              a check-in, and nothing else: a relaunch here would be a second
              copy of the run beside the first.
    gone      nothing of the run is alive. Alert and check in — or, for a run
              launched with --resume-on-gone and under its cap, relaunch the
              recorded command. The resume rests on supervisor and command
              sharing a scope: they died together, of the same outside cause.
    gone, after orphaned
              the orphan has exited. Its exit was not observed (it may have
              finished, crashed or been halted by a guard), so it is never
              resumed automatically."""
    n = n_orphaned = 0
    for p in (state_dir() / "runs").glob("*.json"):
        try:
            r = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if r.get("state") not in LIVE_STATES or liveness(r) == "supervised":
            continue
        was_orphaned = r["state"] == "orphaned"
        alive = command_alive(r)
        if alive:
            if not was_orphaned:
                r.update(state="orphaned", orphaned_since=_now())
                _write_json(p, r)
                n_orphaned += 1
                rec = alert(r["name"], "orphaned", f"supervisor pid {r.get('supervisor_pid')} is dead and the command "
                            f"is still alive ({alive}): nothing was relaunched, and nothing watches it for a stall or "
                            f"records its exit. To recover: {_orphan_advice(r)}", r.get("dir"), r.get("tag", "anvil"))
                if checkin_mode(r.get("checkin_requested") or r.get("checkin")) == "claude":
                    llm_checkin(rec, r)
            continue
        r.update(state="gone", ended=_now())
        _write_json(p, r)
        log = Path(r["log"]) if r.get("log") else None
        tail = _tail(log) if log and log.exists() else "(no log)"
        n += 1
        if not was_orphaned and r.get("resume") and r.get("resume_count", 0) < r.get("resume_max", 3):
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
        why = ("the orphaned command has exited and its exit was not observed (it is not resumed automatically)"
               if was_orphaned else f"supervisor pid {r.get('supervisor_pid')} is dead (reboot / OOM / kill)")
        rec = alert(r["name"], "gone", f"{why}; the run's last log lines:\n{tail}", r.get("dir"), r.get("tag", "anvil"))
        # resolved now, from the request: a launch-time `none` (an expired login) must not
        # also silence the one event the supervisor cannot report itself
        if checkin_mode(r.get("checkin_requested") or r.get("checkin")) == "claude":
            llm_checkin(rec, r)
    print(f"swept {n} gone run(s)" + (f", {n_orphaned} orphaned" if n_orphaned else ""))
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
    if argv[:1] == ["_supervise"]:  # the detached supervisor re-executing itself (_scope_argv); not a user verb
        return _supervise_entry()
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
    la.add_argument("--memory-max", default=None, help="e.g. 20G: MemoryMax on the run's systemd scope (the command and its supervisor), where available")
    la.add_argument("--tag", default="anvil")
    la.add_argument("--foreground", action="store_true", help="supervise in this process (tests, chains)")
    la.add_argument("--checkin", default=None, choices=["auto", "claude", "none"],
                    help="the LLM check-in on failed / stalled / gone / orphaned / long done (auto = claude when the CLI "
                         "is on PATH; $ANVIL_CHECKIN overrides)")
    la.add_argument("--no-selftest", action="store_true", help="skip the launch-time claude -p self-test")
    la.add_argument("--no-memsampler", action="store_true",
                    help="do not arm the memory sampler + watchdog user unit for this launch (10-29: every detached "
                         "launch arms it; ANVIL_MEMSAMPLER=0 is the environment's off switch)")
    la.add_argument("--launched-by", default=os.environ.get("ANVIL_LAUNCHED_BY") or None, metavar="SESSION",
                    help="the launching Claude session as ListAgents names it to ITSELF, name and ref: "
                         "'<name> [<ref>]' (10-03/10-04). The check-in relays the run's events to the session "
                         "whose row carries that bracketed ref (peers see a titled session by its title, not its "
                         "name; the ref is the same from every side), so the launcher — who owns the close — is "
                         "woken and no peer writes a second record; unset = the relay falls back to any live "
                         "anvil session ($ANVIL_LAUNCHED_BY is the default)")
    la.add_argument("--watch", action="append", default=None, metavar="GLOB",
                    help="extra artifact roots for the stall tick (a glob; repeatable), e.g. 'data/runs/b4post-*'")
    la.add_argument("--resume-on-gone", action="store_true",
                    help="the sweep relaunches this run's recorded command when it finds the supervisor dead and "
                         "nothing of the run alive (a reboot, an OOM kill of the run's scope) — for a command that "
                         "resumes from its own state, e.g. selfplay. A dead supervisor over a live command reads "
                         "`orphaned` and is never relaunched")
    la.add_argument("--resume-max", type=int, default=3,
                    help="the relaunch cap under --resume-on-gone (a crash loop stops); the count starts over at "
                         "every manual `relaunch`")
    la.add_argument("--resume-count", type=int, default=0, help=argparse.SUPPRESS)
    pa = sub.add_parser("pause", help="write STOP for the run's command, mark it paused when it exits (no FAILED push)")
    pa.add_argument("--name", required=True)
    pa.add_argument("--now", action="store_true", help="also SIGTERM the command's process group: every process of the run's tree gets it itself")
    pa.add_argument("--wait", action="store_true", help="block until the run has exited")
    pa.add_argument("--scope", choices=("loop", "all"), default="loop",
                    help="loop (default): STOP in the run dir + watched loop roots, never a loop's live "
                         "harness dirs (a harness-only run still drains); all: every watched dir (09-21)")
    rl = sub.add_parser("relaunch", help="re-run a paused / gone / failed / done run's recorded command in place (STOP files removed)")
    rl.add_argument("--name", required=True)
    rl.add_argument("--no-selftest", action="store_true")
    rl.add_argument("--checkin", default=None, choices=["auto", "claude", "none"],
                    help="the check-in mode for this and later relaunches (11-09); default: the mode the run was "
                         "launched with, resolved and self-tested again — never the last launch's resolution")
    rl.add_argument("--launched-by", default=None, metavar="SESSION",
                    help="re-point the run's launching session (its ListAgents name [ref]) before the relaunch — "
                         "the check-in relays to it and it owns the close (ADR-0107); default: the recorded one")
    st = sub.add_parser("status")
    st.add_argument("--json", action="store_true")
    wa = sub.add_parser("wait", help="block until the run is done (0) / failed (1) / gone (2) / paused (4) / "
                                     "orphaned (5); 3 = --timeout")
    wa.add_argument("--name", required=True)
    wa.add_argument("--timeout", type=float, default=0)
    wa.add_argument("--poll", type=float, default=10.0)
    tk = sub.add_parser("tick", help="read-only: what the stall tick sees for a run right now (the newest counted "
                                     "file and its age, the launcher's own files it does not count)")
    tk.add_argument("--name", required=True)
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
            "sweep": lambda: sweep(a), "install-sweep": lambda: install_sweep(a), "tick": lambda: tick(a),
            "pause": lambda: pause(a), "relaunch": lambda: relaunch(a)}[a.verb]()


if __name__ == "__main__":
    sys.exit(main())
