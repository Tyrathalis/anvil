#!/usr/bin/env python3
"""Unload ComfyUI's models after a quiet spell (a user timer runs this once a minute).

Busy = a job running or pending (GET /prompt), a new history entry since the last
poll (a job finished between polls), or the daemon's SM share above a trickle.
Idle for COMFY_IDLE_S (600) while the daemon still holds >= COMFY_VRAM_MB (2048)
of VRAM -> POST /free {unload_models, free_memory}: the worker unloads every model,
resets its output cache and runs gc, releasing the VRAM and the host-RAM offload
that otherwise idle beside the box's training runs. Logs before/after memory.
Exits 0 quietly when the daemon is down or unreachable.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE = os.environ.get("COMFY_URL", "http://100.106.120.33:8188")
IDLE_S = float(os.environ.get("COMFY_IDLE_S", "600"))
VRAM_MB = float(os.environ.get("COMFY_VRAM_MB", "2048"))
UNIT = os.environ.get("COMFY_UNIT", "comfyui.service")
STATE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "comfyui-idle-unload.json"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.load(r)


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status


def main_pid():
    out = subprocess.run(["systemctl", "--user", "show", "-p", "MainPID", "--value", UNIT], capture_output=True, text=True).stdout.strip()
    return int(out or 0)


def vram_mb(pid):
    out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"], capture_output=True, text=True)
    if out.returncode != 0:
        return None
    for line in out.stdout.splitlines():
        p, _, mem = line.partition(",")
        if p.strip() == str(pid):
            try:
                return float(mem.strip())
            except ValueError:
                return None
    return 0.0


def sm_pct(pid):
    out = subprocess.run(["nvidia-smi", "pmon", "-c", "1", "-s", "u"], capture_output=True, text=True)
    for line in out.stdout.splitlines():
        f = line.split()
        if len(f) > 3 and f[1] == str(pid):
            try:
                return float(f[3])
            except ValueError:
                return 0.0
    return 0.0


def rss_mb(pid):
    try:
        for line in open(f"/proc/{pid}/status"):
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) // 1024
    except OSError:
        pass
    return None


def main():
    now = time.time()
    try:
        state = json.loads(STATE.read_text())
    except (OSError, ValueError):
        state = {}
    pid = main_pid()
    if not pid:
        return 0
    try:
        remaining = get("/prompt")["exec_info"]["queue_remaining"]
        hist = get("/history?max_items=1")
        head = next(iter(hist), None)
    except Exception:  # noqa: BLE001 — the daemon is down or starting
        return 0
    sm = sm_pct(pid)
    busy = remaining > 0 or (head is not None and head != state.get("head")) or sm >= 5
    if busy or "idle_since" not in state:
        state.update(idle_since=now, head=head)
        STATE.write_text(json.dumps(state))
        return 0
    fb = vram_mb(pid)
    if fb is None or fb < VRAM_MB:
        STATE.write_text(json.dumps(state))
        return 0
    idle = now - state["idle_since"]
    if idle < IDLE_S:
        return 0
    before = (fb, rss_mb(pid))
    try:
        status = post("/free", {"unload_models": True, "free_memory": True})
    except Exception as e:  # noqa: BLE001
        print(f"[comfyui-idle-unload] /free failed: {e}", file=sys.stderr)
        return 0
    time.sleep(15)
    after = (vram_mb(pid), rss_mb(pid))
    print(f"[comfyui-idle-unload] idle {idle:.0f} s with {before[0]:.0f} MB held: POST /free ({status}) — vram {before[0]:.0f} -> {after[0]:.0f} MB, rss {before[1]} -> {after[1]} MB", flush=True)
    state["last_free"] = now
    state["idle_since"] = now
    STATE.write_text(json.dumps(state))
    return 0


if __name__ == "__main__":
    sys.exit(main())
