"""VRAM elasticity (task #12): OOM-catch-retry in the RL learner's
segmented forwards, gradient-accumulating batch split in the critic
phase, and the driver's free-VRAM seg autotune. OOM is simulated (stub
models raising torch.cuda.OutOfMemoryError above a size threshold) so
the recovery paths run on CPU."""

from __future__ import annotations

import torch

import anvil.training.rl as rl_mod
from anvil.training.finetune_value import _train_batch
from anvil.training.selfplay import _auto_seg


class _CountingNet(torch.nn.Module):
    """Stands in for the policy net in forward_segments: raises OOM for
    segments larger than `fits`, records the sizes it actually served."""

    def __init__(self, fits: int):
        super().__init__()
        self.fits = fits
        self.served: list[int] = []

    def forward(self, seg):
        b = seg["x"].shape[0]
        if b > self.fits:
            raise torch.cuda.OutOfMemoryError(f"stub OOM at {b}")
        self.served.append(b)
        return {"x": seg["x"] * 2}


def _stub_collate(exs):
    return {"x": torch.stack([e["x"] for e in exs])}


def test_forward_segments_halves_on_oom_and_sticks(monkeypatch):
    monkeypatch.setattr(rl_mod, "collate", _stub_collate)
    fs = rl_mod.make_forward_segments("cpu", seg=32)
    net = _CountingNet(fits=10)
    exs = [{"x": torch.full((3,), float(i))} for i in range(50)]
    outs = [seg["x"] for seg, _ in fs(net, exs, grad=False)]
    # 32 -> 16 (OOM) -> 8 (OOM, fits): all examples served, order preserved
    assert torch.cat(outs).shape[0] == 50
    assert torch.equal(torch.cat(outs)[:, 0], torch.arange(50, dtype=torch.float32))
    assert all(b <= 8 for b in net.served)
    # the reduction sticks across calls of the same factory instance
    net2 = _CountingNet(fits=10)
    list(fs(net2, exs[:20], grad=False))
    assert all(b <= 8 for b in net2.served)


def test_forward_segments_raises_at_floor(monkeypatch):
    monkeypatch.setattr(rl_mod, "collate", _stub_collate)
    fs = rl_mod.make_forward_segments("cpu", seg=16)
    net = _CountingNet(fits=0)  # nothing ever fits
    exs = [{"x": torch.zeros(3)} for _ in range(4)]
    try:
        list(fs(net, exs, grad=False))
        raise AssertionError("expected OutOfMemoryError at the seg floor")
    except torch.cuda.OutOfMemoryError:
        pass


class _ValueNet(torch.nn.Module):
    """Stands in for the critic in _train_batch: linear value head over a
    per-example feature; OOM above `fits` examples (None = never)."""

    def __init__(self, fits: int | None = None):
        super().__init__()
        self.lin = torch.nn.Linear(4, 1)
        self.fits = fits

    def forward(self, batch):
        b = batch["feat"].shape[0]
        if self.fits is not None and b > self.fits:
            raise torch.cuda.OutOfMemoryError(f"stub OOM at {b}")
        return {"value_logit": self.lin(batch["feat"]).squeeze(-1)}


def _value_batch(n=16, seed=0):
    g = torch.Generator().manual_seed(seed)
    return {"feat": torch.randn(n, 4, generator=g),
            "has_outcome": torch.ones(n, dtype=torch.int64),
            "won": (torch.rand(n, generator=g) < 0.5).to(torch.int64)}


def test_train_batch_split_matches_whole_batch_gradient():
    batch = _value_batch()
    denom = int(batch["has_outcome"].sum())

    whole = _ValueNet()
    split = _ValueNet(fits=4)  # forces two levels of halving
    split.load_state_dict(whole.state_dict())

    loss_whole = _train_batch(whole, batch, "cpu", denom)
    loss_split = _train_batch(split, batch, "cpu", denom)

    # sum-loss/denom accumulated over halves == whole-batch mean BCE;
    # tolerance covers bf16-autocast summation-order differences
    assert abs(loss_whole - loss_split) < 2e-2
    for pw, ps in zip(whole.parameters(), split.parameters()):
        assert torch.allclose(pw.grad, ps.grad, atol=2e-2, rtol=5e-2)


def test_train_batch_raises_at_single_example():
    net = _ValueNet(fits=0)
    batch = _value_batch(n=2)
    try:
        _train_batch(net, batch, "cpu", 2)
        raise AssertionError("expected OutOfMemoryError at batch of one")
    except torch.cuda.OutOfMemoryError:
        pass


def test_auto_seg_table_pin_and_fallback(monkeypatch):
    import anvil.training.selfplay as sp

    def fake_smi(free_mb):
        class R:
            stdout = f"{free_mb}\n"
        return lambda *a, **k: R()

    monkeypatch.setattr(sp.subprocess, "run", fake_smi(20000))
    assert _auto_seg(0) == 256
    monkeypatch.setattr(sp.subprocess, "run", fake_smi(12000))
    assert _auto_seg(0) == 128
    monkeypatch.setattr(sp.subprocess, "run", fake_smi(4000))
    assert _auto_seg(0) == 64
    assert _auto_seg(128) == 128  # pinned: no probe consulted

    def boom(*a, **k):
        raise FileNotFoundError("no nvidia-smi")
    monkeypatch.setattr(sp.subprocess, "run", boom)
    assert _auto_seg(0) == 128  # conservative fallback
