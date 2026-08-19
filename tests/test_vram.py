"""VRAM elasticity helpers (anvil/training/vram.py, 2026-08-18)."""

from anvil.training.vram import seg_tier, wait_for_vram


def test_seg_tier_matches_autotune_thresholds():
    assert seg_tier(20000) == 256
    assert seg_tier(16000) == 256
    assert seg_tier(15999) == 128
    assert seg_tier(9000) == 128
    assert seg_tier(8999) == 64
    assert seg_tier(100) == 64


def test_wait_for_vram_returns_immediately_when_free():
    polls = wait_for_vram("t", min_free_mb=1000, _free=lambda: 2000, _sleep=lambda s: None)
    assert polls == 0


def test_wait_for_vram_parks_until_recovery():
    vals = iter([500, 800, 1200, 9500])  # entry read + 3 polls
    sleeps: list[float] = []
    notes: list[tuple] = []
    polls = wait_for_vram(
        "t",
        min_free_mb=9000,
        poll_s=7,
        _free=lambda: next(vals),
        _sleep=sleeps.append,
        _notify=lambda *a: notes.append(a),
    )
    assert polls == 3
    assert sleeps == [7, 7, 7]
    assert len(notes) == 1  # notified once, on entering the parked state


def test_park_for_cotenant_refuses_without_scarcity(monkeypatch):
    # CUDA absent (the CPU test env): a floor OOM is not a scarcity
    # problem — caller must re-raise (the legacy floor-test contract)
    import anvil.training.vram as v

    monkeypatch.setattr(v.torch.cuda, "is_available", lambda: False)
    assert v.park_for_cotenant("t") is False
