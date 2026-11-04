"""The training step's GPU gate (selfplay._wait_gpu_free, 11-03): the loop
waits for a foreign GPU job under the harness's own yield rule before it
launches the trainer (big-run iteration 367 CUDA-OOMed in loss.backward()
beside ComfyUI's 17.5 GB job), the wait is reported, and yield.json takes
the seconds beside gen_s."""

import json

from anvil.bridge.harness import gpu_yield as gy
from anvil.training import selfplay as sp

COMFY = gy.GpuProc(pid=1793, kind="C", sm=99.0, fb_mb=17450.0, name="python")
KWIN = gy.GpuProc(pid=2723, kind="C+G", sm=0.0, fb_mb=140.0, name="kwin_wayland")


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


def _yielder(samples, clock, monkeypatch):
    """A GpuYield over a scripted pmon sequence (the last sample repeats)."""
    monkeypatch.setattr(gy, "_sid", lambda pid: 5)  # every process foreign by session
    monkeypatch.setattr(gy, "_is_anvil_server", lambda pid: False)
    it = iter(samples)
    last = [samples[-1]]

    def sampler():
        try:
            last[0] = next(it)
        except StopIteration:
            pass
        return last[0]

    return gy.GpuYield(own_sid=77, on_s=0.0, off_s=60.0, sample_s=30.0, sampler=sampler, clock=clock)


def test_quiet_card_returns_zero(monkeypatch):
    clk = Clock()
    y = _yielder([[KWIN]], clk, monkeypatch)
    assert sp._wait_gpu_free("iteration 1: training step", yielder=y, sleep=clk.advance) == 0.0


def test_waits_out_a_foreign_job_and_reports(monkeypatch, capsys):
    clk = Clock()
    # ComfyUI holds the card for three samples, then only the compositor is left
    y = _yielder([[COMFY, KWIN]] * 3 + [[KWIN]], clk, monkeypatch)
    waited = sp._wait_gpu_free("iteration 367: training step", yielder=y, sleep=clk.advance)
    # 3 held samples + the 60 s off-hysteresis, in 30 s polls
    assert waited >= 90.0
    out = capsys.readouterr().out
    assert "GPU held by python[1793] 17450 MB sm 99%" in out
    assert "GPU quiet after" in out and "training" in out


def test_no_nvidia_smi_never_waits(monkeypatch):
    clk = Clock()
    y = gy.GpuYield(own_sid=77, on_s=0.0, sampler=lambda: None, clock=clk)
    assert sp._wait_gpu_free("iteration 1: training step", yielder=y, sleep=clk.advance) == 0.0


def test_note_yield_merges_beside_gen_s(tmp_path):
    p = tmp_path / "yield.json"
    p.write_text(json.dumps({"gen_s": 545.0}) + "\n")
    sp._note_yield(p, "train_wait_s", 120.4)
    sp._note_yield(p, "train_wait_s", 30.0)
    d = json.loads(p.read_text())
    assert d == {"gen_s": 545.0, "train_wait_s": 150.4}
    # a fresh file (no generation yield recorded) still takes the key
    q = tmp_path / "fresh.json"
    sp._note_yield(q, "train_wait_s", 1.0)
    assert json.loads(q.read_text()) == {"train_wait_s": 1.0}

