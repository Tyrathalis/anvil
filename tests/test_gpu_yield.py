"""The GPU yield (the crude autoscaler, 09-14): pmon parsing, the foreign
rule (outside our session AND actually using the card), the hysteresis."""

from anvil.bridge.harness import gpu_yield as gy

PMON = """\
# gpu         pid   type     sm    mem    enc    dec    jpg    ofa     fb   ccpm    command
# Idx           #    C/G      %      %      %      %      %      %     MB     MB    name
    0       1750     C      -      -      -      -      -      -    386      0    python
    0       2390   C+G      -      -      -      -      -      -    137      0    kwin_wayland
    0       2498     G      -      -      -      -      -      -    113      0    plasmashell
    0       9001     C     85     40      -      -      -      -   9120      0    python
    0       9002     C      3      1      -      -      -      -   1400      0    python
"""


def test_parse_pmon_by_header():
    ps = {p.pid: p for p in gy.parse_pmon(PMON)}
    assert ps[1750].fb_mb == 386 and ps[1750].sm == 0 and ps[1750].kind == "C"
    assert ps[9001].fb_mb == 9120 and ps[9001].sm == 85
    assert ps[2498].kind == "G"
    assert ps[9001].name == "python"


def test_foreign_rule(monkeypatch):
    procs = gy.parse_pmon(PMON)
    # 9001 is ours (same sid); 9002 uses 1.4 GB from another session; 1750 idle
    monkeypatch.setattr(gy, "_sid", lambda pid: 77 if pid == 9001 else 5)
    monkeypatch.setattr(gy, "_is_anvil_server", lambda pid: False)
    f = gy.foreign_procs(procs, own_sid=77)
    assert [p.pid for p in f] == [9002]
    # an Anvil model server from another session is still ours
    monkeypatch.setattr(gy, "_is_anvil_server", lambda pid: pid == 9002)
    assert gy.foreign_procs(procs, own_sid=77) == []
    # everything foreign: the graphics-only and the idle context still do not count
    monkeypatch.setattr(gy, "_sid", lambda pid: 5)
    monkeypatch.setattr(gy, "_is_anvil_server", lambda pid: False)
    assert sorted(p.pid for p in gy.foreign_procs(procs, own_sid=77)) == [9001, 9002]


def test_hysteresis(monkeypatch):
    monkeypatch.setattr(gy, "_sid", lambda pid: 5)
    monkeypatch.setattr(gy, "_is_anvil_server", lambda pid: False)
    now = {"t": 0.0}
    state = {"procs": []}
    y = gy.GpuYield(own_sid=77, on_s=60, off_s=120, sample_s=30,
                    sampler=lambda: state["procs"], clock=lambda: now["t"])
    busy = [gy.GpuProc(9001, "C", 85, 9120, "python")]

    def step(dt, procs):
        now["t"] += dt
        state["procs"] = procs
        return y.poll()

    assert step(0, []) is False
    assert step(30, busy) is False       # present since t=30
    assert step(30, busy) is False       # held 30 s < 60
    assert step(30, busy) is True        # held 60 s -> yielding
    assert step(30, []) is True          # absent since t=120
    assert step(60, []) is True          # 60 s absent < 120
    assert step(60, []) is False         # 120 s absent -> resumed
    # a sample within sample_s is skipped (state unchanged)
    state["procs"] = busy
    now["t"] += 10
    assert y.poll() is False
    assert y.describe() == ""


def test_no_nvidia_smi_never_yields():
    y = gy.GpuYield(own_sid=1, sampler=lambda: None, clock=lambda: 1e6)
    assert y.poll() is False
