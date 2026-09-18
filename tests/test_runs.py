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
    monkeypatch.setenv("ANVIL_CHECKIN", "none")  # never the real CLI from a test
    monkeypatch.delenv("ANVIL_NOTIFY_CMD", raising=False)
    return tmp_path


def _launch(tmp, name, cmd, **kw):
    args = ["launch", "--name", name, "--dir", str(tmp / name), "--tick-sec", "0.2", "--foreground"]
    for k, v in kw.items():
        args += [f"--{k.replace('_', '-')}"] + ([] if v is True else [str(v)])
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


# ---------------------------------------------------------------- the LLM check-in (ADR-0107 addendum 09-18)


@pytest.fixture()
def claude_shim(state, monkeypatch):
    """A fake `claude` on PATH: records argv + the prompt, answers OK."""
    b = state / "bin"
    b.mkdir()
    rec = state / "claude-calls.txt"
    (b / "claude").write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" >> {rec}\n"
        f"[ -t 0 ] || cat >> {rec}\n"  # the prompt arrives on stdin
        f"printf -- '---\\n' >> {rec}\n"
        "echo OK\n"
    )
    (b / "claude").chmod(0o755)
    monkeypatch.setenv("PATH", f"{b}:{os.environ['PATH']}")
    monkeypatch.delenv("ANVIL_CHECKIN", raising=False)
    return rec


def test_checkin_runs_on_failure_and_records_itself(state, claude_shim):
    rc = _launch(state, "cf", ["sh", "-c", "echo kaboom; exit 2"], checkin="claude")
    assert rc == 1
    calls = claude_shim.read_text()
    assert "Reply with exactly the word OK" in calls  # the launch self-test
    assert 'run "cf" is FAILED' in calls and "kaboom" in calls and "--allowedTools" in calls
    kinds = [a["kind"] for a in runs.read_alerts()]
    assert kinds == ["failed", "checkin"]
    assert runs.read_alerts()[-1]["msg"].startswith("for failed ")
    assert runs.read_run("cf")["checkin"] == "claude"


def test_short_done_does_not_check_in(state, claude_shim):
    rc = _launch(state, "cd", ["true"], checkin="claude", no_selftest=True)
    assert rc == 0
    assert not claude_shim.exists()
    assert [a["kind"] for a in runs.read_alerts()] == ["done"]


def test_stall_checks_in_once(state, claude_shim):
    d = state / "cs"
    cmd = ["sh", "-c", f"sleep 1.6; touch {d}/x; sleep 0.6; exit 0"]
    rc = _launch(state, "cs", cmd, stall_sec=1, checkin="claude", no_selftest=True)
    assert rc == 0
    for _ in range(50):  # the stall's check-in runs off-thread
        if claude_shim.exists() and "is STALLED" in claude_shim.read_text():
            break
        time.sleep(0.1)
    assert 'run "cs" is STALLED' in claude_shim.read_text()
    kinds = [a["kind"] for a in runs.read_alerts()]
    assert kinds.count("checkin") == 1 and kinds[-1] == "done"


def test_failed_selftest_downgrades_to_none_and_alerts(state, monkeypatch):
    b = state / "bin"
    b.mkdir()
    (b / "claude").write_text("#!/bin/sh\necho 'Failed to authenticate: OAuth session expired' >&2\nexit 1\n")
    (b / "claude").chmod(0o755)
    monkeypatch.setenv("PATH", f"{b}:{os.environ['PATH']}")
    monkeypatch.delenv("ANVIL_CHECKIN", raising=False)
    rc = _launch(state, "cx", ["sh", "-c", "exit 1"], checkin="auto")
    assert rc == 1
    kinds = [a["kind"] for a in runs.read_alerts()]
    assert kinds == ["checkin_unavailable", "failed"]  # no checkin record: the consumer was absent
    assert "OAuth" in runs.read_alerts()[0]["msg"]
    assert runs.read_run("cx")["checkin"] == "none"


def test_sweep_marks_gone_and_checks_in(state, claude_shim):
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    os.waitpid(pid, 0)  # a pid that is certainly dead
    d = state / "gone"
    d.mkdir()
    (d / "run.log").write_text("working...\nKilled\n")
    runs._write_json(runs._run_file("gone"), {
        "name": "gone", "state": "running", "pid": 1, "supervisor_pid": pid, "started": runs._now(),
        "cmd": ["x"], "dir": str(d), "log": str(d / "run.log"), "checkin": "claude", "tag": "anvil",
    })
    assert runs.main(["sweep"]) == 0
    assert runs.read_run("gone")["state"] == "gone"
    kinds = [a["kind"] for a in runs.read_alerts()]
    assert kinds == ["gone", "checkin"]
    assert 'run "gone" is GONE' in claude_shim.read_text() and "Killed" in claude_shim.read_text()
    assert runs.main(["sweep"]) == 0 and len(runs.read_alerts()) == 2  # idempotent


def test_watch_roots_keep_a_chain_from_false_stalling(state):
    """A chain that writes its arms OUTSIDE its own dir (the 09-17 read) stays
    `running` when --watch names those roots; without it the same run stalls."""
    arms = state / "arms"
    arms.mkdir()
    d = state / "wc"
    cmd = ["sh", "-c", f"sleep 0.6; touch {arms}/x-s0; sleep 0.6; touch {arms}/x-s1; sleep 0.6; exit 0"]
    rc = _launch(state, "wc", cmd, stall_sec=1, watch=str(arms / "x-*"))
    assert rc == 0
    assert [a["kind"] for a in runs.read_alerts()] == ["done"]
    assert runs.read_run("wc")["watch"] == [str(arms / "x-*")]
