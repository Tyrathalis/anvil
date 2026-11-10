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
    monkeypatch.setenv("ANVIL_MEMSAMPLER", "0")  # never the box's user unit from a test
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


def test_checkin_relays_to_the_launching_session(state, claude_shim):
    """10-03: the event goes to the launcher (who owns the close), not to every
    'anvil' session; unset -> the fallback, said so in the prompt."""
    rc = _launch(state, "cl", ["sh", "-c", "exit 2"], checkin="claude", launched_by="bridge-abc-7f")
    assert rc == 1
    calls = claude_shim.read_text()
    assert 'send ONE message to the session named "bridge-abc-7f"' in calls
    assert "owns its record" in calls and "do not write its close" in calls
    assert runs.read_run("cl")["launched_by"] == "bridge-abc-7f"
    assert runs._relaunch_args(runs.read_run("cl")).launched_by == "bridge-abc-7f"
    rc = _launch(state, "cu", ["sh", "-c", "exit 2"], checkin="claude")
    assert rc == 1
    assert "recorded no launching session" in claude_shim.read_text()
    assert runs.read_run("cu")["launched_by"] is None
    # 10-04: with a ref the relay matches the bracketed id, not the name (peers list a
    # titled session by its title)
    rc = _launch(state, "cr", ["sh", "-c", "exit 2"], checkin="claude", launched_by="bridge-abc-7f [33c4ae]")
    assert rc == 1
    assert "whose row carries the ref [33c4ae]" in claude_shim.read_text()


def test_wait_heartbeats_its_own_run(state, monkeypatch):
    """10-03: `anvil.runs wait` inside a launched run writes the waiting run's
    heartbeat.json each poll, so a queue's benign wait is not a stall."""
    d = state / "q"
    d.mkdir()
    runs._write_json(runs._run_file("q"), {"name": "q", "state": "running", "dir": str(d), "pid": 1})
    runs._write_json(runs._run_file("target"), {"name": "target", "state": "done", "rc": 0, "dir": str(state / "t")})
    monkeypatch.setenv("ANVIL_RUN_NAME", "q")
    runs._HEARTBEAT_LAST[0] = 0.0
    assert runs.main(["wait", "--name", "target"]) == 0
    hb = json.loads((d / "heartbeat.json").read_text())
    assert hb["note"] == "waiting on target"


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
    cmd = ["sh", "-c", f"sleep 0.6; touch {arms}/x-s0; sleep 0.6; touch {arms}/x-s1; sleep 0.6; exit 0"]
    rc = _launch(state, "wc", cmd, stall_sec=1, watch=str(arms / "x-*"))
    assert rc == 0
    assert [a["kind"] for a in runs.read_alerts()] == ["done"]
    assert runs.read_run("wc")["watch"] == [str(arms / "x-*")]


# ---- 09-21: pause / relaunch / the sweep's auto-resume / the heartbeat


def test_pause_records_paused_not_failed_and_relaunch_resumes(state):
    d = state / "pz"
    d.mkdir()
    # the command honours STOP in its dir (selfplay's contract), else runs 30 s
    cmd = ["sh", "-c", f"for i in $(seq 1 60); do [ -f {d}/STOP ] && exit 0; sleep 0.5; done; exit 7"]
    rc = runs.main(["launch", "--name", "pz", "--dir", str(d), "--tick-sec", "0.2", "--", *cmd])
    assert rc == 0
    time.sleep(0.5)
    assert runs.main(["pause", "--name", "pz", "--wait"]) == 0
    st = runs.read_run("pz")
    assert st["state"] == "paused" and st["stop_files"] == [str(d / "STOP")]
    kinds = [a["kind"] for a in runs.read_alerts()]
    assert "failed" not in kinds and kinds[-1] == "paused"
    assert (d / "STOP").exists()
    # relaunch: the STOP file goes, the same command runs again and finishes
    (d / "again").write_text("")
    cmd2_marker = d / "STOP"
    assert runs.main(["relaunch", "--name", "pz", "--no-selftest"]) == 0
    assert not cmd2_marker.exists()
    deadline = time.time() + 40
    while time.time() < deadline and (runs.read_run("pz") or {}).get("state") in ("running", "stalled"):
        (d / "STOP").write_text("")  # let the second incarnation exit cleanly
        time.sleep(0.5)
    st = runs.read_run("pz")
    assert st["state"] == "done", st
    assert st["cmd"] == cmd


def test_relaunch_launched_by_overrides_the_recorded_session(state):
    """10-21: a relaunch from a new session re-points the run's owner; without the
    flag the recorded session stays (the relay would otherwise fall back on a dead ref)."""
    rc = _launch(state, "lb", ["sh", "-c", "exit 0"], launched_by="old-session [aaaaaa]")
    assert rc == 0 and runs.read_run("lb")["launched_by"] == "old-session [aaaaaa]"
    assert _relaunch_args_of("lb").launched_by == "old-session [aaaaaa]"
    assert _relaunch_args_of("lb", "new-session [bbbbbb]").launched_by == "new-session [bbbbbb]"
    assert runs.main(["relaunch", "--name", "lb", "--no-selftest", "--launched-by", "new-session [bbbbbb]"]) == 0
    _wait_done("lb")
    assert runs.read_run("lb")["launched_by"] == "new-session [bbbbbb]"
    assert runs.main(["relaunch", "--name", "lb", "--no-selftest"]) == 0
    _wait_done("lb")
    assert runs.read_run("lb")["launched_by"] == "new-session [bbbbbb]"


def _relaunch_args_of(name, launched_by=None):
    return runs._relaunch_args(runs.read_run(name), True, launched_by)


def _wait_done(name, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline and (runs.read_run(name) or {}).get("state") in ("running", "stalled"):
        time.sleep(0.2)
    assert runs.read_run(name)["state"] == "done", runs.read_run(name)


def test_pause_on_a_finished_run_is_refused(state):
    assert _launch(state, "fin", ["true"]) == 0
    assert runs.main(["pause", "--name", "fin"]) == 3
    assert runs.main(["pause", "--name", "nope"]) == 2


def test_sweep_relaunches_a_gone_run_under_the_cap(state):
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    os.waitpid(pid, 0)
    d = state / "res"
    d.mkdir()
    (d / "run.log").write_text("working...\n")
    base = {
        "name": "res", "state": "running", "pid": 1, "supervisor_pid": pid, "started": runs._now(),
        "cmd": ["sh", "-c", "exit 0"], "dir": str(d), "log": str(d / "run.log"), "checkin": "none",
        "tag": "anvil", "launch_cwd": os.getcwd(), "watch": [], "resume": True, "resume_max": 2,
        "resume_count": 0, "tick_sec": 0.2, "stall_sec": 60,
    }
    runs._write_json(runs._run_file("res"), dict(base))
    assert runs.main(["sweep"]) == 0
    kinds = [a["kind"] for a in runs.read_alerts()]
    assert kinds[0] == "relaunched"
    deadline = time.time() + 20
    while time.time() < deadline and runs.read_run("res")["state"] != "done":
        time.sleep(0.2)
    st = runs.read_run("res")
    assert st["state"] == "done" and st["resume_count"] == 1 and st["resume"] is True
    # over the cap: gone, not relaunched
    runs._write_json(runs._run_file("res"), dict(base, resume_count=2))
    assert runs.main(["sweep"]) == 0
    assert runs.read_run("res")["state"] == "gone"
    assert [a["kind"] for a in runs.read_alerts()][-1] == "gone"


def test_heartbeat_touches_the_run_dir_only_inside_a_launch(state, monkeypatch):
    monkeypatch.delenv("ANVIL_RUN_NAME", raising=False)
    runs._HEARTBEAT_LAST[0] = 0.0
    assert runs.heartbeat("x") is False
    d = state / "hb"
    d.mkdir()
    runs._write_json(runs._run_file("hb"), {"name": "hb", "state": "running", "dir": str(d)})
    monkeypatch.setenv("ANVIL_RUN_NAME", "hb")
    assert runs.heartbeat("gpu yield") is True
    assert json.loads((d / "heartbeat.json").read_text())["note"] == "gpu yield"
    assert runs.heartbeat("again") is False  # throttled


# ---- 09-27: the pause's STOP scope (the 09-23 truncated generation)


def test_pause_scope_skips_a_loops_live_harness_dirs(state):
    """A chain watched with a glob that matches both its loop root and the
    harness dirs the loop launched: STOP lands in the run dir + the loop root
    only (the loop stops at its iteration boundary; the generation finishes)."""
    d = state / "chain"
    d.mkdir()
    arms = state / "arms"
    loop = arms / "sd-alloc"
    loop.mkdir(parents=True)
    (loop / "loop_state.json").write_text("{}")
    gen = arms / "sd-alloc-i004-main-x"
    (gen / "workers").mkdir(parents=True)
    (gen / "run.json").write_text("{}")  # the harness's pinning manifest (09-28: not manifest.json)
    other = arms / "sd-notes"
    other.mkdir()
    r = {"dir": str(d), "watch": [str(arms / "sd-*")]}
    got = {p.name for p in runs._stop_roots(r)}
    assert got == {"chain", "sd-alloc", "sd-notes"}
    assert {p.name for p in runs._stop_roots(r, "all")} == {"chain", "sd-alloc", "sd-alloc-i004-main-x", "sd-notes"}
    # a harness-only run (no loop root watched) still drains at game granularity
    (loop / "loop_state.json").unlink()
    assert {p.name for p in runs._stop_roots(r)} == {"chain", "sd-alloc", "sd-alloc-i004-main-x", "sd-notes"}


def test_pause_default_scope_writes_stop_to_loop_roots_only(state):
    d = state / "pz2"
    d.mkdir()
    arms = state / "arms2"
    loop = arms / "l-a"
    loop.mkdir(parents=True)
    (loop / "loop_state.json").write_text("{}")
    gen = arms / "l-a-i000-main"
    (gen / "workers").mkdir(parents=True)
    (gen / "run.json").write_text("{}")  # the harness's pinning manifest (09-28: not manifest.json)
    cmd = ["sh", "-c", f"for i in $(seq 1 60); do [ -f {d}/STOP ] && exit 0; sleep 0.5; done; exit 7"]
    rc = runs.main(["launch", "--name", "pz2", "--dir", str(d), "--tick-sec", "0.2",
                    "--watch", str(arms / "l-*"), "--", *cmd])
    assert rc == 0
    time.sleep(0.5)
    assert runs.main(["pause", "--name", "pz2", "--wait"]) == 0
    st = runs.read_run("pz2")
    assert st["state"] == "paused"
    assert sorted(st["stop_files"]) == sorted([str(d / "STOP"), str(loop / "STOP")])
    assert not (gen / "STOP").exists()


class _Fake:
    """A systemctl / systemd-run stand-in: `active` answers is-active; every call is logged."""

    def __init__(self, active: bool, rc: int = 0):
        self.active, self.rc, self.calls = active, rc, []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if cmd[:3] == ["systemctl", "--user", "is-active"]:
            return subprocess.CompletedProcess(cmd, 0 if self.active else 3)
        if cmd[0] == "systemctl" and cmd[2] == "stop":
            self.active = False
        return subprocess.CompletedProcess(cmd, self.rc if cmd[0] == "systemd-run" else 0, "", "boom")


def test_memsampler_arms_when_inactive_and_records_the_owner(state, monkeypatch):
    monkeypatch.setenv("ANVIL_MEMSAMPLER", "1")
    fake = _Fake(active=False)
    note = runs.arm_memsampler("r1", state / "r1", run=fake)
    assert note.startswith("memory watchdog: ARMED") and str(state / "r1" / "memory.jsonl") in note
    assert any(c[0] == "systemd-run" for c in fake.calls)
    rec = json.loads((runs.state_dir() / "memsampler.json").read_text())
    assert rec["run"] == "r1" and rec["out"].endswith("r1/memory.jsonl")


def test_memsampler_left_alone_for_a_live_owner_and_retaken_from_a_dead_one(state, monkeypatch):
    monkeypatch.setenv("ANVIL_MEMSAMPLER", "1")
    runs._write_json(runs.state_dir() / "memsampler.json", {"run": "owner", "out": "x/memory.jsonl"})
    # the owner is live: left alone, no systemd-run
    runs._write_json(runs._run_file("owner"), {"name": "owner", "state": "running", "supervisor_pid": os.getpid()})
    fake = _Fake(active=True)
    assert runs.arm_memsampler("r2", state / "r2", run=fake).startswith("memory watchdog: active (armed by owner")
    assert not any(c[0] == "systemd-run" for c in fake.calls)
    # the same run relaunching: left alone too
    assert "active" in runs.arm_memsampler("owner", state / "owner", run=_Fake(active=True))
    # the owner finished: stopped and re-armed toward the new run
    runs._write_json(runs._run_file("owner"), {"name": "owner", "state": "done", "supervisor_pid": os.getpid()})
    fake = _Fake(active=True)
    note = runs.arm_memsampler("r2", state / "r2", run=fake)
    assert note.startswith("memory watchdog: ARMED")
    assert ["systemctl", "--user", "stop", runs.MEMSAMPLER_UNIT] in fake.calls
    assert json.loads((runs.state_dir() / "memsampler.json").read_text())["run"] == "r2"


def test_memsampler_failure_is_a_phrase_not_an_exception(state, monkeypatch):
    monkeypatch.setenv("ANVIL_MEMSAMPLER", "1")
    note = runs.arm_memsampler("r3", state / "r3", run=_Fake(active=False, rc=1))
    assert "FAILED to arm" in note and "unwatched" in note
    monkeypatch.setenv("ANVIL_MEMSAMPLER", "0")
    assert runs.arm_memsampler("r3", state / "r3", run=_Fake(active=False)) == "memory watchdog: off (ANVIL_MEMSAMPLER=0)"


# ---- 11-09: the stall tick does not count the launcher's own files (the infrastructure survey, finding 1)


def test_sampler_file_in_the_run_dir_does_not_mask_a_stall(state):
    """The quickstart's layout: --dir is the loop dir and the memory sampler
    appends <dir>/memory.jsonl every 20 s. A loop that has gone quiet is
    STALLED however fresh the sampler's file is (the big run's tick was blind
    for five weeks)."""
    d = state / "loop"
    d.mkdir()
    (d / "loop_state.json").write_text("{}")
    cmd = ["sh", "-c", f"for i in $(seq 1 14); do touch {d}/memory.jsonl; sleep 0.2; done; exit 0"]
    assert _launch(state, "loop", cmd, stall_sec=1) == 0
    kinds = [a["kind"] for a in runs.read_alerts()]
    assert kinds == ["stalled", "done"], kinds


def test_heartbeat_still_holds_the_stall_off(state):
    """A job idle on purpose stays `running`: heartbeat.json is an artifact."""
    d = state / "hbs"
    cmd = ["sh", "-c", f"for i in $(seq 1 14); do touch {d}/heartbeat.json; sleep 0.2; done; exit 0"]
    assert _launch(state, "hbs", cmd, stall_sec=1) == 0
    assert [a["kind"] for a in runs.read_alerts()] == ["done"]


def test_another_runs_sampler_output_under_a_watch_root_is_ignored(state):
    """The box has one sampler; its owner's dir can sit under this run's --watch
    glob. memsampler.json names the file and the tick skips it there too."""
    arms = state / "arms"
    (arms / "br-read").mkdir(parents=True)
    out = arms / "br-read" / "memory.jsonl"
    runs._write_json(runs.state_dir() / "memsampler.json", {"run": "br-read", "out": str(out)})
    old = time.time() - 3600
    (arms / "br-read" / "games.jsonl").write_text("{}\n")
    os.utime(arms / "br-read" / "games.jsonl", (old, old))
    out.write_text("{}\n")
    ignore = runs.stall_ignored(state / "chain")
    assert runs.newest_mtime(arms / "br-read", ignore) == pytest.approx(old, abs=1)
    assert runs.newest_mtime(arms / "br-read") > old + 3000  # uncounted only through the ignore set
    assert runs.newest_mtime(out, ignore) == 0.0  # a --watch glob that names the file itself
    # a file of the same NAME that is not the sampler's still counts
    (arms / "br-read" / "sub").mkdir()
    (arms / "br-read" / "sub" / "memory.jsonl").write_text("{}\n")
    assert runs.newest_mtime(arms / "br-read", ignore) > old + 3000


def test_a_detached_stall_does_not_recover_on_the_supervisors_own_log(state):
    """Detached, the supervisor's stdout is <dir>/supervisor.log: raising STALLED
    wrote to the watched dir and the next tick said `recovered` (all eight
    stalls in the queue up to 11-09 recovered exactly one tick later)."""
    d = state / "dst"
    # a real subprocess: under pytest's capture an in-process fork keeps the captured sys.stdout
    out = subprocess.run(
        [sys.executable, "-m", "anvil.runs", "launch", "--name", "dst", "--dir", str(d), "--tick-sec", "0.2",
         "--stall-sec", "1", "--", "sh", "-c", "sleep 3; exit 0"],
        capture_output=True, text=True, env=dict(os.environ), timeout=30,
    )
    assert out.returncode == 0, out.stderr
    _wait_done("dst")
    kinds = [a["kind"] for a in runs.read_alerts()]
    assert "STALLED" in (d / "supervisor.log").read_text()  # the supervisor did write into the watched dir
    assert kinds == ["stalled", "done"], kinds


# ---- 11-09: the check-in is re-resolved on every relaunch (the infrastructure survey, finding 2)


def test_relaunch_resolves_the_checkin_again(state, monkeypatch):
    """One failed self-test (the 10-16 expired login) recorded `checkin: none`
    and every relaunch reused it. The state now keeps what was REQUESTED; a
    relaunch resolves and self-tests it again, and --checkin overrides."""
    b = state / "bin"
    b.mkdir()
    shim = b / "claude"
    shim.write_text("#!/bin/sh\necho 'Failed to authenticate: OAuth session expired' >&2\nexit 1\n")
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", f"{b}:{os.environ['PATH']}")
    monkeypatch.delenv("ANVIL_CHECKIN", raising=False)
    assert _launch(state, "ck", ["sh", "-c", "exit 0"], checkin="auto") == 0
    st = runs.read_run("ck")
    assert st["checkin"] == "none" and st["checkin_requested"] == "auto"
    assert runs._relaunch_args(st).checkin == "auto"  # not the resolved none
    # the login is back: the relaunch self-tests and the check-in is on again
    rec = state / "claude-calls.txt"
    shim.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> {rec}\necho OK\n")
    assert runs.main(["relaunch", "--name", "ck"]) == 0
    _wait_done("ck")
    st = runs.read_run("ck")
    assert st["checkin"] == "claude" and st["checkin_requested"] == "auto"
    assert "Reply with exactly the word OK" in rec.read_text()
    # --checkin overrides, and the override is what later relaunches resolve
    assert runs.main(["relaunch", "--name", "ck", "--checkin", "none"]) == 0
    _wait_done("ck")
    st = runs.read_run("ck")
    assert st["checkin"] == "none" and st["checkin_requested"] == "none"
    assert runs._relaunch_args(st).checkin == "none"
    # a state file from before the field (the big run's): no request on record -> auto
    legacy = {k: v for k, v in st.items() if k != "checkin_requested"}
    assert runs._relaunch_args(legacy).checkin == "auto"
    assert runs._relaunch_args(legacy, checkin="none").checkin == "none"


# ---- 11-09: `wait` ends on every terminal state (the infrastructure survey, finding 7)


def test_wait_returns_on_paused_and_on_a_swept_gone(state):
    """done 0 / failed 1 / gone 2 / paused 4. A `gone` the sweep already wrote
    and a `paused` used to match no branch: without --timeout the wait never
    returned (with it, 3 — the timeout — which is what this would read)."""
    d = str(state / "x")
    runs._write_json(runs._run_file("wp"), {"name": "wp", "state": "paused", "dir": d, "supervisor_pid": 1})
    assert runs.main(["wait", "--name", "wp", "--timeout", "3", "--poll", "0.2"]) == 4
    runs._write_json(runs._run_file("wg"), {"name": "wg", "state": "gone", "dir": d, "supervisor_pid": 1})
    assert runs.main(["wait", "--name", "wg", "--timeout", "3", "--poll", "0.2"]) == 2
    # the unswept form (running, the supervisor dead) is the same answer
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    os.waitpid(pid, 0)
    runs._write_json(runs._run_file("wr"), {"name": "wr", "state": "running", "dir": d, "supervisor_pid": pid})
    assert runs.main(["wait", "--name", "wr", "--timeout", "3", "--poll", "0.2"]) == 2
    # a live run still waits: the timeout is the only way out
    runs._write_json(runs._run_file("wl"), {"name": "wl", "state": "running", "dir": d, "supervisor_pid": os.getpid()})
    assert runs.main(["wait", "--name", "wl", "--timeout", "0.6", "--poll", "0.2"]) == 3


# ---- 11-09: the sweep's resume budget starts over at a manual relaunch (the infrastructure survey, finding 9)


def test_manual_relaunch_resets_the_resume_count(state):
    """The cap stops a crash loop; it is not a budget for the run's life. The
    sweep's own resume keeps counting (test_sweep_relaunches_a_gone_run_under_the_cap)."""
    d = state / "rc"
    d.mkdir()
    runs._write_json(runs._run_file("rc"), {
        "name": "rc", "state": "gone", "pid": 1, "supervisor_pid": 1, "started": runs._now(),
        "cmd": ["sh", "-c", "exit 0"], "dir": str(d), "log": str(d / "run.log"), "tag": "anvil",
        "launch_cwd": os.getcwd(), "watch": [], "resume": True, "resume_max": 3, "resume_count": 3,
        "tick_sec": 0.2, "stall_sec": 60,
    })
    assert runs._relaunch_args(runs.read_run("rc")).resume_count == 3  # the sweep's path: carried
    assert runs.main(["relaunch", "--name", "rc", "--no-selftest"]) == 0
    _wait_done("rc")
    st = runs.read_run("rc")
    assert st["resume_count"] == 0 and st["resume"] is True and st["resume_max"] == 3


# ---- 11-09: one arm for the memory sampler, the launcher's (the infrastructure survey, R2)


def test_memsampler_is_rearmed_after_a_reboot_for_the_same_owner(state, monkeypatch):
    """A reboot kills the transient unit and leaves memsampler.json naming the
    run that owned it. The relaunch of that same run (by hand, or the sweep's
    resume) finds the unit inactive and arms it again — the case the chain's
    own arm existed for before the launcher took the job."""
    monkeypatch.setenv("ANVIL_MEMSAMPLER", "1")
    runs._write_json(runs.state_dir() / "memsampler.json", {"run": "big", "out": "old/memory.jsonl"})
    runs._write_json(runs._run_file("big"), {"name": "big", "state": "gone", "supervisor_pid": 1})
    fake = _Fake(active=False)
    note = runs.arm_memsampler("big", state / "big", run=fake)
    assert note.startswith("memory watchdog: ARMED") and str(state / "big" / "memory.jsonl") in note
    assert sum(c[0] == "systemd-run" for c in fake.calls) == 1
    assert json.loads((runs.state_dir() / "memsampler.json").read_text())["out"].endswith("big/memory.jsonl")


def test_the_big_run_chain_reports_the_sampler_and_never_arms_it():
    """One mechanism per job: the chain starts no unit. It still reads the trip
    marker the launcher's sampler writes beside this run's memory.jsonl."""
    from pathlib import Path

    chain = Path(__file__).resolve().parents[1] / "scripts" / "big_run_chain.sh"
    text = chain.read_text()
    code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    assert "systemd-run" not in code and "arm_memsampler" not in code
    assert "report_memsampler" in code and '"$OUT/WATCHDOG-TRIP"' in code
    assert subprocess.run(["bash", "-n", str(chain)], capture_output=True).returncode == 0


# ---- 11-09: `tick`, the read-only view of the stall tick (the boundary's self-check)


def test_tick_shows_what_the_stall_tick_counts(state, capsys):
    d = state / "tk"
    d.mkdir()
    old = time.time() - 600
    (d / "loop.log").write_text("x\n")
    os.utime(d / "loop.log", (old, old))
    (d / "memory.jsonl").write_text("{}\n")  # fresh, and not the run's progress
    started = runs.datetime.fromtimestamp(old - 60).astimezone().isoformat(timespec="seconds")
    runs._write_json(runs._run_file("tk"), {"name": "tk", "state": "running", "dir": str(d), "stall_sec": 300,
                                            "started": started, "watch": [], "supervisor_pid": os.getpid()})
    before = sorted(p.name for p in d.iterdir())
    assert runs.main(["tick", "--name", "tk"]) == 1  # 600 s of silence against a 300 s alarm
    out = capsys.readouterr().out
    assert "loop.log" in out.splitlines()[0] and "STALLED" in out.splitlines()[0]
    assert "not counted" in out and "memory.jsonl" in out
    (d / "heartbeat.json").write_text("{}")  # idle on purpose: counted
    assert runs.main(["tick", "--name", "tk"]) == 0
    assert "heartbeat.json" in capsys.readouterr().out.splitlines()[0]
    assert sorted(p.name for p in d.iterdir()) == sorted(before + ["heartbeat.json"])  # the verb wrote nothing
    assert runs.read_run("tk")["state"] == "running" and not runs.read_alerts()
    assert runs.main(["tick", "--name", "nope"]) == 2
