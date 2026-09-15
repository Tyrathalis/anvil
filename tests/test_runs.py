"""anvil.runs (ADR-0107): the launcher records failure as a state, ticks its
own stall check, and queues an alert on every transition."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import pytest

from anvil import runs


@pytest.fixture()
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("ANVIL_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("ANVIL_NOTIFY_SILENT", "1")
    monkeypatch.delenv("ANVIL_NOTIFY_CMD", raising=False)
    return tmp_path


def _launch(tmp, name, cmd, **kw):
    args = ["launch", "--name", name, "--dir", str(tmp / name), "--tick-sec", "0.2", "--foreground"]
    for k, v in kw.items():
        args += [f"--{k.replace('_', '-')}", str(v)]
    return runs.main(args + ["--"] + cmd)


def test_fast_failure_is_a_recorded_state(state):
    rc = _launch(state, "ff", ["sh", "-c", "echo boom; exit 3"])
    assert rc == 1
    r = runs.read_run("ff")
    assert r["state"] == "failed" and r["rc"] == 3
    al = runs.read_alerts()
    assert [a["kind"] for a in al] == ["failed"]
    assert "boom" in al[0]["msg"] and not al[0]["acked"]


def test_clean_finish(state):
    rc = _launch(state, "ok", ["sh", "-c", "echo hi; exit 0"])
    assert rc == 0
    assert runs.read_run("ok")["state"] == "done"
    assert [a["kind"] for a in runs.read_alerts()] == ["done"]
    assert "hi" in (state / "ok" / "run.log").read_text()


def test_stall_then_recover_then_done(state):
    d = state / "st"
    cmd = ["sh", "-c", f"sleep 1.6; touch {d}/x; sleep 0.6; exit 0"]
    rc = _launch(state, "st", cmd, stall_sec=1)  # 1 s of silence = a stall; ticks at 0.2 s
    assert rc == 0
    kinds = [a["kind"] for a in runs.read_alerts()]
    assert kinds[0] == "stalled" and "recovered" in kinds and kinds[-1] == "done"
    assert runs.read_run("st")["state"] == "done"


def test_ack_and_unacked_view(state):
    _launch(state, "a1", ["true"])
    _launch(state, "a2", ["false"])
    assert len(runs.read_alerts(unacked_only=True)) == 2
    ids = {runs.read_alerts()[0]["id"]}
    assert runs.ack_alerts(ids) == 1
    left = runs.read_alerts(unacked_only=True)
    assert len(left) == 1 and left[0]["run"] == "a2"
    assert runs.ack_alerts(None) == 1


def test_detached_launch_prints_coverage_and_outlives_the_shell(state):
    d = state / "det"
    env = dict(os.environ, ANVIL_STATE_DIR=str(state / "state"), ANVIL_NOTIFY_SILENT="1")
    out = subprocess.run(
        [sys.executable, "-m", "anvil.runs", "launch", "--name", "det", "--dir", str(d), "--tick-sec", "0.2",
         "--", "sh", "-c", "sleep 0.5; exit 0"],
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert out.returncode == 0, out.stderr
    line = out.stdout.strip()
    assert line.startswith("[runs] LAUNCHED det") and "stall alarm" in line and "sinks queue" in line
    for _ in range(100):
        r = json.loads((state / "state" / "runs" / "det.json").read_text())
        if r["state"] == "done":
            break
        time.sleep(0.1)
    assert r["state"] == "done" and r["rc"] == 0
    assert "sleep 0.5" in (d / "run.log").read_text()


def test_wait_and_status(state):
    _launch(state, "w", ["true"])
    assert runs.main(["wait", "--name", "w", "--timeout", "5"]) == 0
    _launch(state, "wf", ["false"])
    assert runs.main(["wait", "--name", "wf", "--timeout", "5"]) == 1
    assert runs.main(["status"]) == 0
