"""The model server's first-window stall (the arm reads' BridgePoisoned
games): the schedule surface's card table is built once per process, under a
lock and in the warm-up, and a slow answer or a slow batch says so in the
server log.

The stall was a race on a lazy global. Each gRPC stream thread that reached
`sched_targets.card_table()` before the first build finished started its own
build of about 35,000 parsed card scripts; N concurrent builds take about
2 s x N under the GIL, and twelve outlast the workers' 20 s bridge deadline.
"""

import threading
import time
from collections import Counter
from types import SimpleNamespace

import torch

from anvil.bridge import server as srv
from anvil.bridge.server import AskClock, DecisionServicer, ModelBackend, _Batcher
from anvil.training import sched_targets


def _slow_build(calls: list, delay: float = 0.2):
    def build():
        calls.append(threading.get_ident())
        time.sleep(delay)  # long enough for every other thread to arrive
        return {"Plains": object()}

    return build


def test_card_table_builds_once_under_concurrent_first_calls(monkeypatch):
    import veto_knowability

    calls: list = []
    monkeypatch.setattr(veto_knowability, "build_card_table", _slow_build(calls))
    monkeypatch.setattr(sched_targets, "_TABLE", None)
    got: list = []
    start = threading.Barrier(8)

    def ask():
        start.wait(timeout=5)
        got.append(sched_targets.card_table())

    ths = [threading.Thread(target=ask) for _ in range(8)]
    for t in ths:
        t.start()
    for t in ths:
        t.join(timeout=10)
    assert len(calls) == 1  # one build; seven threads waited for it
    assert len(got) == 8 and all(g is got[0] for g in got)
    assert sched_targets.card_table() is got[0] and len(calls) == 1  # and it is kept


class _Feat:
    def example(self, dec, header, task):
        return {"task": torch.tensor(0), "entities": torch.zeros(1, 1)}, {}


class _Submit:
    def __init__(self):
        self.n = 0

    def submit(self, ex, pass_delta, noise):
        self.n += 1
        return {}


def test_warmup_builds_the_card_table_only_for_a_schedule_checkpoint(monkeypatch, capsys):
    import veto_knowability

    calls: list = []
    monkeypatch.setattr(veto_knowability, "build_card_table", _slow_build(calls, delay=0.0))
    monkeypatch.setattr(sched_targets, "_TABLE", None)

    plain = SimpleNamespace(feat=_Feat(), batcher=_Submit(), sched_serve=None)
    ModelBackend.warmup(plain)
    assert calls == [] and plain.batcher.n == 3  # no schedule surface: nothing to build

    sched = SimpleNamespace(feat=_Feat(), batcher=_Submit(), sched_serve=object())
    ModelBackend.warmup(sched)
    assert len(calls) == 1 and sched.batcher.n == 3
    out = capsys.readouterr().out
    assert "warm-up: card table 1 entries" in out


def test_warmup_survives_a_card_table_error(monkeypatch, capsys):
    import veto_knowability

    def boom():
        raise OSError("no Forge checkout")

    monkeypatch.setattr(veto_knowability, "build_card_table", boom)
    monkeypatch.setattr(sched_targets, "_TABLE", None)
    be = SimpleNamespace(feat=_Feat(), batcher=_Submit(), sched_serve=object())
    ModelBackend.warmup(be)  # best-effort: logged, never fatal
    out = capsys.readouterr().out
    assert "card table skipped" in out and be.batcher.n == 3


def test_ask_clock_line_names_each_phase():
    clk = AskClock()
    clk.mark("featurize")
    time.sleep(0.03)
    clk.mark("sched_inject")
    line = clk.line("mtg.priority seq=3 worker=w g=7")
    assert line.startswith("SLOW ASK mtg.priority seq=3 worker=w g=7: ")
    assert "featurize 0.00" in line and "sched_inject 0.0" in line


class _SlowBackend:
    """answer() spends its time in one phase, as the card-table race did
    (in the schedule hook after the forward)."""

    def __init__(self, delay):
        self.delay = delay

    def answer(self, req, header, game_seed=None, greedy=False, clock=None):
        clock.mark("featurize")
        clock.mark("sched_inject")
        clock.mark("queue+forward")
        time.sleep(self.delay)
        clock.mark("sched_after")
        return srv.pb.DecisionResponse(decision_seq=req.decision_seq)


def _req(seq=3):
    return srv.pb.DecisionRequest(game_id="g7", decision_seq=seq, decision_tag="mtg.priority")


def test_slow_answer_prints_one_line_with_the_slow_phase(capsys):
    sv = DecisionServicer("model", ["mtg.priority"], backend=_SlowBackend(0.08), slow_ask_s=0.05)
    resp = sv._model_answer(_req(), {"g": 7}, worker="anvil-worker-r48")
    assert resp.decision_seq == 3 and not resp.fallback
    lines = [ln for ln in capsys.readouterr().out.splitlines() if "SLOW ASK" in ln]
    assert len(lines) == 1
    assert "mtg.priority seq=3 worker=anvil-worker-r48 g=7" in lines[0]
    assert "sched_after 0.0" in lines[0] and "queue+forward 0.00" in lines[0]


def test_fast_answer_and_disabled_threshold_print_nothing(capsys):
    fast = DecisionServicer("model", ["mtg.priority"], backend=_SlowBackend(0.0), slow_ask_s=0.05)
    fast._model_answer(_req(), {"g": 7})
    off = DecisionServicer("model", ["mtg.priority"], backend=_SlowBackend(0.08), slow_ask_s=0)
    off._model_answer(_req(), {"g": 7})
    assert "SLOW ASK" not in capsys.readouterr().out


def test_slow_ask_lines_are_capped(monkeypatch, capsys):
    monkeypatch.setattr(srv, "SLOW_LINE_CAP", 2)
    sv = DecisionServicer("model", ["mtg.priority"], backend=_SlowBackend(0.02), slow_ask_s=0.01)
    for seq in range(1, 6):
        sv._model_answer(_req(seq), {"g": 7})
    lines = [ln for ln in capsys.readouterr().out.splitlines() if "SLOW ASK" in ln]
    assert len(lines) == 3 and "suppressed" in lines[-1]


class _SleepNet:
    def __init__(self, delay):
        self.delay = delay

    def act(self, batch, pass_delta=0.0, noise=None, temperature=1.0, sched_decode=False):
        time.sleep(self.delay)
        return {"choice": torch.zeros(batch["entities"].shape[0], dtype=torch.int64), "n_ent": 1}


def _batcher(monkeypatch, delay, slow_forward_s):
    monkeypatch.setattr("anvil.training.dataset.collate", lambda exs: {"entities": torch.zeros(len(exs), 1)})
    return _Batcher(
        _SleepNet(delay), torch, "cpu", Counter(), max_batch=8, window_ms=5.0, autocast=False,
        stats_every=0, slow_forward_s=slow_forward_s,
    )


def _wait_for(capsys, needle: str, timeout: float = 2.0) -> str:
    """The batcher prints after it releases the caller; poll for the line."""
    out, t0 = "", time.monotonic()
    while needle not in out and time.monotonic() - t0 < timeout:
        time.sleep(0.01)
        out += capsys.readouterr().out
    return out


def test_slow_batch_prints_its_size_and_phase_times(monkeypatch, capsys):
    b = _batcher(monkeypatch, delay=0.08, slow_forward_s=0.05)
    out = b.submit({"task": torch.tensor(0), "entities": torch.zeros(5, 3)}, 0.0, None)
    assert int(out["choice"][0]) == 0
    line = next(ln for ln in _wait_for(capsys, "SLOW FORWARD").splitlines() if "SLOW FORWARD" in ln)
    assert "batch 1" in line and "tasks {0: 1}" in line and "max entities 5" in line
    assert "act 0.0" in line or "act 0.1" in line


def test_fast_batch_prints_nothing(monkeypatch, capsys):
    b = _batcher(monkeypatch, delay=0.0, slow_forward_s=0.05)
    b.submit({"task": torch.tensor(0), "entities": torch.zeros(5, 3)}, 0.0, None)
    time.sleep(0.05)
    assert "SLOW FORWARD" not in capsys.readouterr().out
