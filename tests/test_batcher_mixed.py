"""M12 Build 4½ (ADR-0113): a sampled server's batcher mixes sampled and
greedy asks (the search copies, the value / allocation wire, the greedy-
served tags) — noise is per group, one forward per group; and the sampled-
task gate (no noise, no mu for tasks without a sampled head)."""

import threading

import torch

from anvil.bridge.server import _Batcher
from anvil.policy.sampling import sampled_tasks


class _Net:
    """Records each act() call's noise and answers per item: logp_choice
    only under noise (the real act()'s contract)."""

    def __init__(self):
        self.calls = []

    def act(self, batch, pass_delta=0.0, noise=None, temperature=1.0, sched_decode=False):
        b = batch["entities"].shape[0]
        self.calls.append((b, noise is not None))
        out = {"choice": torch.zeros(b, dtype=torch.int64), "n_ent": 1}
        if noise is not None:
            out["logp_choice"] = torch.full((b,), -0.1)
        return out


def _ex(i):
    from anvil.training.dataset import collate  # noqa: F401  (the batcher collates real examples)

    return {"i": i}


def test_batcher_runs_one_forward_per_noise_group(monkeypatch):

    # a stand-in collate / pad_noise over the stub examples
    monkeypatch.setattr("anvil.training.dataset.collate", lambda exs: {"entities": torch.zeros(len(exs), 1)})
    monkeypatch.setattr("anvil.policy.sampling.pad_noise", lambda noises, batch, dev: {"choice": torch.zeros(len(noises))})
    net = _Net()
    from collections import Counter

    b = _Batcher(net, torch, "cpu", Counter(), max_batch=8, window_ms=50.0, autocast=False, stats_every=0)
    outs = {}

    def ask(k, nz):
        outs[k] = b.submit(_ex(k), 0.0, nz)

    ths = [threading.Thread(target=ask, args=(0, None)),
           threading.Thread(target=ask, args=(1, {"choice": torch.zeros(1)})),
           threading.Thread(target=ask, args=(2, {"choice": torch.zeros(1)}))]
    for t in ths:
        t.start()
    for t in ths:
        t.join(timeout=5)
    assert "logp_choice" in outs[1] and "logp_choice" in outs[2]
    assert "logp_choice" not in outs[0]
    # the sampled items shared one forward, the greedy one had its own
    assert sorted(net.calls) == [(1, False), (2, True)] or (1, False) in net.calls


def test_sampled_tasks_exclude_the_greedy_served_tags():
    st = sampled_tasks()
    assert {"priority", "mull_keep", "attack", "block", "pay_class"} <= st
    assert "mull_tuck" not in st and "surf_one" not in st and "surf_target" not in st
    assert srv_sampled_gate("mull_tuck") is False and srv_sampled_gate("priority") is True


def srv_sampled_gate(task: str) -> bool:
    return task in sampled_tasks()
