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


def notify(title: str, msg: str, tag: str = "anvil") -> None:
    """Try $ANVIL_NOTIFY_CMD (an executable, invoked with title and message as
    its two arguments — wire ntfy/kdeconnect/mail there), then notify-send as
    the at-desk fallback. Never raises: no notification path may kill the job
    it exists to report on."""
    print(f"[{tag}] NOTIFY: {title} — {msg}", flush=True)
    cmds = []
    if os.environ.get("ANVIL_NOTIFY_CMD"):
        cmds.append([os.environ["ANVIL_NOTIFY_CMD"], title, msg])
    cmds.append(["notify-send", "--urgency=critical", "--app-name=anvil",
                 title, msg])
    for cmd in cmds:
        if shutil.which(cmd[0]) is None:
            continue
        try:
            subprocess.run(cmd, timeout=30, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:  # noqa: BLE001
            print(f"[{tag}] notify via {cmd[0]} failed: {e}", flush=True)
