#!/usr/bin/env python3
"""Standing run watcher (anvil-watch.timer entry point).

Sessions REGISTER long-running processes by dropping a JSON file into
~/.local/state/anvil/watch/ (the registration interface — no command-line
pattern matching anywhere: the 2026-07-31 post-mortem found the ad-hoc
watchers' `pgrep -f` matching their own quoted command lines, so the
babysitters kept each other's liveness checks satisfied after the driver
died). Identity is (pid, /proc starttime, boot time): unforgeable, immune
to pid reuse, and a changed boot time turns a stale registration into a
"machine rebooted while run X was live" alert on the first tick after
power returns.

Verbs:
  register --name N --pid P --dir D [--stall-min M]   (from a launch)
  unregister --name N                                 (clean shutdown)
  check                                               (the timer tick)
  status                                              (human summary)

States per registration, notified on TRANSITION only (dedup lives in
watch-state.json, outside every watched tree — the ad-hoc watcher's
breadcrumb lived inside its watched dir and re-armed itself every tick):
  RUNNING -> STALLED   no file under dir modified in stall_min minutes
  STALLED -> RUNNING   recovered (fresh artifact seen)
  *       -> GONE      pid dead or reboot; registration removed after
                       notifying (clean exits unregister first, so GONE
                       always means "died without cleanup — check logs")

Stdlib only, zero repo imports: the watcher must keep working while the
repo tree is mid-run-frozen, mid-rebase, or broken.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ANVIL_WATCH_DIR override = test seam; state file lives BESIDE the
# registration dir, never inside any watched tree.
WATCH_DIR = Path(os.environ.get("ANVIL_WATCH_DIR") or Path.home() / ".local/state/anvil/watch")
STATE_PATH = WATCH_DIR.parent / "watch-state.json"


def _notify(title: str, msg: str) -> None:
    print(f"[watchd] NOTIFY: {title} — {msg}", flush=True)
    if os.environ.get("ANVIL_NOTIFY_SILENT"):
        return  # test seam (sibling of ANVIL_WATCH_DIR): the stdout line is
        # the assertable event; without this, every suite run popped a real
        # "anvil t2 GONE" desktop alert from the fabricated-crash test
    cmds = []
    if os.environ.get("ANVIL_NOTIFY_CMD"):
        cmds.append([os.environ["ANVIL_NOTIFY_CMD"], title, msg])
    cmds.append(["notify-send", "--urgency=critical", "--app-name=anvil", title, msg])
    for cmd in cmds:
        if shutil.which(cmd[0]) is None:
            continue
        try:
            subprocess.run(
                cmd, timeout=30, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception as e:  # noqa: BLE001
            print(f"[watchd] notify via {cmd[0]} failed: {e}", flush=True)


def _boot_btime() -> int:
    """Boot time as seconds since epoch. Linux via /proc/stat; macOS via sysctl."""
    try:
        with open("/proc/stat") as f:
            for line in f:
                if line.startswith("btime "):
                    return int(line.split()[1])
    except OSError:
        pass
    try:
        out = subprocess.run(
            ["sysctl", "-n", "kern.boottime"], capture_output=True, text=True, check=True, timeout=5
        ).stdout.strip()
        # '{ sec = 1234567890, usec = 0 } Mon Jan  1 00:00:00 2024'
        return int(out.split("=")[1].split(",")[0].strip())
    except Exception:  # noqa: BLE001
        return -1


def _proc_starttime(pid: int) -> int | None:
    """starttime (clock ticks since boot), field 22 of /proc/<pid>/stat;
    parsed from after the last ')' — comm may contain spaces/parens.

    macOS fallback: `ps -o lstart= -p <pid>` gives wall-clock start; convert
    to ticks-since-boot via boot time. Falls back to wall-clock epoch seconds
    if boot time unavailable — still enough for identity stability within a
    boot session and cross-platform tests.
    """
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        return int(stat.rsplit(")", 1)[1].split()[19])
    except OSError:
        pass
    try:
        out = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        ).stdout.strip()
        if not out:
            return None
        start_ts = int(time.mktime(time.strptime(out, "%a %b %d %H:%M:%S %Y")))
        btime = _boot_btime()
        if btime and btime > 0:
            return start_ts - btime
        return start_ts  # epoch seconds fallback
    except Exception:  # noqa: BLE001
        return None


def _newest_mtime(root: Path) -> float:
    newest = 0.0
    for dirpath, _, files in os.walk(root):
        for f in files:
            try:
                newest = max(newest, os.path.getmtime(os.path.join(dirpath, f)))
            except OSError:
                continue
    return newest


def register(a: argparse.Namespace) -> None:
    st = _proc_starttime(a.pid)
    if st is None:
        sys.exit(f"FATAL: pid {a.pid} not running — register with the live driver pid")
    WATCH_DIR.mkdir(parents=True, exist_ok=True)
    rec = {
        "name": a.name,
        "pid": a.pid,
        "starttime": st,
        "btime": _boot_btime(),
        "dir": str(Path(a.dir).resolve()),
        "stall_min": a.stall_min,
        "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (WATCH_DIR / f"{a.name}.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(f"[watchd] registered {a.name}: pid {a.pid} dir {rec['dir']} stall {a.stall_min}m")


def unregister(a: argparse.Namespace) -> None:
    p = WATCH_DIR / f"{a.name}.json"
    if p.exists():
        p.unlink()
        print(f"[watchd] unregistered {a.name}")
    _prune_state({a.name})


def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


def _prune_state(names: set[str]) -> None:
    state = _load_state()
    for n in names:
        state.pop(n, None)
    _save_state(state)


def check(_a: argparse.Namespace) -> None:
    state = _load_state()
    btime = _boot_btime()
    for reg_path in sorted(WATCH_DIR.glob("*.json")) if WATCH_DIR.exists() else []:
        try:
            reg = json.loads(reg_path.read_text())
        except ValueError:
            continue
        name = reg["name"]
        prev = state.get(name, "RUNNING")

        alive = reg.get("btime") == btime and _proc_starttime(reg["pid"]) == reg["starttime"]
        if not alive:
            why = (
                "machine rebooted while it was live"
                if reg.get("btime") != btime
                else "process died without clean shutdown"
            )
            _notify(f"anvil {name} GONE", f"{why} — check {reg['dir']}")
            reg_path.unlink(missing_ok=True)
            state.pop(name, None)
            continue

        age_min = (time.time() - _newest_mtime(Path(reg["dir"]))) / 60
        cur = "STALLED" if age_min > reg["stall_min"] else "RUNNING"
        if cur == "STALLED" and prev != "STALLED":
            _notify(
                f"anvil {name} STALLED", f"no artifact written in {age_min:.0f} min ({reg['dir']})"
            )
        elif cur == "RUNNING" and prev == "STALLED":
            _notify(f"anvil {name} recovered", f"fresh artifacts in {reg['dir']}")
        state[name] = cur
    _save_state(state)


def status(_a: argparse.Namespace) -> None:
    state = _load_state()
    regs = sorted(WATCH_DIR.glob("*.json")) if WATCH_DIR.exists() else []
    if not regs:
        print("[watchd] no registrations")
    for reg_path in regs:
        reg = json.loads(reg_path.read_text())
        alive = (
            reg.get("btime") == _boot_btime() and _proc_starttime(reg["pid"]) == reg["starttime"]
        )
        age = (time.time() - _newest_mtime(Path(reg["dir"]))) / 60
        print(
            f"{reg['name']}: pid {reg['pid']} "
            f"{'alive' if alive else 'DEAD'}, newest artifact {age:.0f}m ago "
            f"(stall at {reg['stall_min']}m), "
            f"state {state.get(reg['name'], '?')}"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="verb", required=True)
    r = sub.add_parser("register")
    r.add_argument("--name", required=True)
    r.add_argument("--pid", type=int, required=True)
    r.add_argument("--dir", required=True)
    r.add_argument("--stall-min", type=int, default=75)
    r.set_defaults(fn=register)
    u = sub.add_parser("unregister")
    u.add_argument("--name", required=True)
    u.set_defaults(fn=unregister)
    sub.add_parser("check").set_defaults(fn=check)
    sub.add_parser("status").set_defaults(fn=status)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
