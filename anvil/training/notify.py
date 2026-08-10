"""Best-effort push for unattended runs.

Lifted out of the selfplay driver (2026-07-26) so every long-running entry
point can report its own end. The driver had this from 2026-07-23; the
2,000-game reads did not, so two ~2h reads finished with nothing telling
anyone — the user had to ask whether notifications were broken. A run that
cannot announce its own completion is a run someone has to babysit.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def watch_register(name: str, watch_dir, stall_min: int = 75) -> None:
    """Best-effort self-registration with the standing watcher
    (scripts/anvil_watchd.py + anvil-watch.timer). The process reports its
    OWN pid — the 2026-07-31 post-mortem retired every pattern-derived pid
    acquisition after `pgrep -f` self-matches claimed three babysitters.
    Clean exits must call watch_unregister; dying without it is the point:
    the watcher then notifies GONE. Never raises."""
    try:
        script = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "anvil_watchd.py")
        subprocess.run(
            [
                sys.executable,
                script,
                "register",
                "--name",
                name,
                "--pid",
                str(os.getpid()),
                "--dir",
                str(watch_dir),
                "--stall-min",
                str(stall_min),
            ],
            timeout=30,
            check=False,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[notify] watch_register failed: {e}", flush=True)


def watch_unregister(name: str) -> None:
    """Clean-shutdown counterpart of watch_register. Never raises."""
    try:
        script = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "anvil_watchd.py")
        subprocess.run(
            [sys.executable, script, "unregister", "--name", name], timeout=30, check=False
        )
    except Exception as e:  # noqa: BLE001
        print(f"[notify] watch_unregister failed: {e}", flush=True)


def notify(title: str, msg: str, tag: str = "anvil") -> None:
    """Try $ANVIL_NOTIFY_CMD (an executable, invoked with title and message as
    its two arguments — wire ntfy/kdeconnect/mail there), then notify-send as
    the at-desk fallback. Never raises: no notification path may kill the job
    it exists to report on."""
    print(f"[{tag}] NOTIFY: {title} — {msg}", flush=True)
    if os.environ.get("ANVIL_NOTIFY_SILENT"):
        return  # test seam — see anvil_watchd._notify
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
            print(f"[{tag}] notify via {cmd[0]} failed: {e}", flush=True)
