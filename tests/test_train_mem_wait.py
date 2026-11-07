"""The training step's host-memory gate (selfplay._wait_host_memory, 11-07):
the loop waits while MemAvailable is under the floor before it launches the
trainer (the learner holds ≈ 35 GB at a step; segment 4's step floor fell to
14 GB beside the box's other tenants), the wait is reported, and yield.json
takes the seconds beside gen_s and train_wait_s."""

import json

from anvil.training import selfplay as sp


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


def _reader(samples):
    it = iter(samples)
    last = [samples[-1]]

    def read():
        try:
            last[0] = next(it)
        except StopIteration:
            pass
        return last[0]

    return read


def test_enough_memory_returns_zero():
    clk = Clock()
    assert sp._wait_host_memory("iteration 1: training step", 40 * 1024.0, reader=_reader([50_000.0]),
                                sleep=clk.advance, clock=clk) == 0.0


def test_waits_out_a_low_floor_and_reports(capsys):
    clk = Clock()
    # 22 GB available while a ComfyUI offload sits beside the user's game, then the offload leaves
    rd = _reader([22_000.0, 22_500.0, 23_000.0, 48_000.0])
    waited = sp._wait_host_memory("iteration 407: training step", 40 * 1024.0, reader=rd, sleep=clk.advance,
                                  clock=clk, poll_s=30.0)
    assert waited == 90.0  # three polls under the floor
    out = capsys.readouterr().out
    assert "MemAvailable 22000 MB under the 40960 MB floor" in out
    assert "host memory 48000 MB after 90 s — training" in out


def test_disabled_or_unreadable_never_waits():
    clk = Clock()
    assert sp._wait_host_memory("x", 0.0, reader=_reader([1.0]), sleep=clk.advance, clock=clk) == 0.0
    assert sp._wait_host_memory("x", 40 * 1024.0, reader=_reader([None]), sleep=clk.advance, clock=clk) == 0.0


def test_mem_available_reader_parses_meminfo(tmp_path):
    f = tmp_path / "meminfo"
    f.write_text("MemTotal:       65432100 kB\nMemFree:         1234567 kB\nMemAvailable:   20480000 kB\n")
    assert sp._mem_available_mb(str(f)) == 20000.0
    assert sp._mem_available_mb(str(tmp_path / "missing")) is None


def test_note_yield_takes_mem_wait_beside_the_others(tmp_path):
    p = tmp_path / "yield.json"
    p.write_text(json.dumps({"gen_s": 545.0, "train_wait_s": 120.0}) + "\n")
    sp._note_yield(p, "mem_wait_s", 300.0)
    assert json.loads(p.read_text()) == {"gen_s": 545.0, "train_wait_s": 120.0, "mem_wait_s": 300.0}
