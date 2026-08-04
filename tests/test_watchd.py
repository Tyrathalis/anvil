"""Standing watcher (scripts/anvil_watchd.py): registration round trip.

Subprocess-driven against a tmp ANVIL_WATCH_DIR — the watcher is
deliberately stdlib-only with no repo imports, so the test exercises the
real CLI surface the driver/read self-registration calls."""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "anvil_watchd.py"


def _run(tmp_path, *args):
    env = {**os.environ, "ANVIL_WATCH_DIR": str(tmp_path / "watch"),
           "ANVIL_NOTIFY_SILENT": "1"}
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          env=env, capture_output=True, text=True, timeout=30)


def test_register_check_unregister_roundtrip(tmp_path):
    r = _run(tmp_path, "register", "--name", "t1", "--pid", str(os.getpid()),
             "--dir", str(tmp_path), "--stall-min", "999")
    assert r.returncode == 0, r.stderr
    reg = json.loads((tmp_path / "watch" / "t1.json").read_text())
    assert reg["pid"] == os.getpid() and reg["starttime"] > 0

    r = _run(tmp_path, "check")
    assert r.returncode == 0
    state = json.loads((tmp_path / "watch-state.json").read_text())
    assert state["t1"] == "RUNNING"

    r = _run(tmp_path, "unregister", "--name", "t1")
    assert r.returncode == 0
    assert not (tmp_path / "watch" / "t1.json").exists()


def test_dead_pid_goes_gone_and_prunes(tmp_path):
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    # register rejects dead pids, so write the registration directly (the
    # crash scenario: registered while alive, died before the tick)
    wd = tmp_path / "watch"
    wd.mkdir(parents=True)
    (wd / "t2.json").write_text(json.dumps(
        {"name": "t2", "pid": proc.pid, "starttime": 12345, "btime": 1,
         "dir": str(tmp_path), "stall_min": 999}))
    r = _run(tmp_path, "check")
    assert r.returncode == 0
    assert "GONE" in r.stdout
    assert not (wd / "t2.json").exists()  # pruned after notifying


def test_register_refuses_dead_pid(tmp_path):
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    r = _run(tmp_path, "register", "--name", "t3", "--pid", str(proc.pid),
             "--dir", str(tmp_path))
    assert r.returncode != 0
